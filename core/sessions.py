"""
Chat session persistence for Katip.
Birden çok sohbet oturumunu tek JSON dosyasında saklar; eski tekil
chat_history.json formatından otomatik migrasyon yapar.
"""
import os
import json
import uuid
import logging
import datetime
from typing import Optional

from core.config import SESSIONS_FILE, CHAT_HISTORY_FILE

logger = logging.getLogger(__name__)

_DEFAULT_TITLE = "Yeni sohbet"
_TITLE_MAX_LEN = 40


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _make_session(messages: Optional[list[dict]] = None) -> dict:
    now = _now_iso()
    return {
        "id": uuid.uuid4().hex,
        "title": _title_from(messages or []),
        "created": now,
        "updated": now,
        "messages": messages or [],
    }


def _title_from(messages: list[dict]) -> str:
    """Oturum başlığını ilk gerçek kullanıcı mesajından türetir."""
    for msg in messages:
        if msg.get("role") != "user":
            continue
        text = (msg.get("content") or "").strip()
        if not text or text.startswith("ARAÇ_SONUCU"):
            continue
        first_line = text.splitlines()[0]
        if len(first_line) > _TITLE_MAX_LEN:
            return first_line[: _TITLE_MAX_LEN - 1] + "…"
        return first_line
    return _DEFAULT_TITLE


class SessionStore:
    """Sohbet oturumlarının diskteki tek yetkili deposu."""

    def __init__(self, path: str = SESSIONS_FILE) -> None:
        self._path = path
        self._sessions: list[dict] = []
        self._active_id: Optional[str] = None
        self.load()

    # ─── Yükleme / Kaydetme ───

    def load(self) -> None:
        """Oturum dosyasını yükler; yoksa eski formattan migrasyon dener."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._sessions = list(data.get("sessions", []))
                self._active_id = data.get("active_id")
            except Exception as e:
                logger.error("Oturum dosyası okunamadı: %s", e)
                self._sessions = []
                self._active_id = None
        elif os.path.exists(CHAT_HISTORY_FILE):
            self._migrate_legacy()

        if not self._sessions:
            self._sessions = [_make_session()]
        if self._active_id not in {s["id"] for s in self._sessions}:
            self._active_id = self._latest_id()

    def _migrate_legacy(self) -> None:
        """Eski chat_history.json'u tek oturuma dönüştürür (dosyaya dokunmaz)."""
        try:
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                messages = json.load(f)
            if isinstance(messages, list) and messages:
                session = _make_session(messages)
                self._sessions = [session]
                self._active_id = session["id"]
                self.save()
                logger.info("Eski sohbet geçmişi yeni oturum formatına taşındı.")
        except Exception as e:
            logger.warning("Eski geçmiş migrasyonu başarısız: %s", e)

    def save(self) -> None:
        """Oturumları atomik olarak diske yazar."""
        data = {"version": 1, "active_id": self._active_id, "sessions": self._sessions}
        tmp_path = self._path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, self._path)
        except Exception as e:
            logger.error("Oturumlar kaydedilemedi: %s", e)

    # ─── Aktif Oturum ───

    @property
    def active_id(self) -> Optional[str]:
        return self._active_id

    def _active(self) -> dict:
        for s in self._sessions:
            if s["id"] == self._active_id:
                return s
        # Tutarsızlık durumunda kendini onar
        self._active_id = self._latest_id()
        return self._sessions[0]

    def active_messages(self) -> list[dict]:
        """Aktif oturumun mesajlarının kopyasını döndürür."""
        return [dict(m) for m in self._active()["messages"]]

    def set_active_messages(self, messages: list[dict]) -> None:
        """Aktif oturumun mesajlarını günceller, başlık/zamanı tazeler ve kaydeder."""
        session = self._active()
        session["messages"] = [dict(m) for m in messages]
        session["title"] = _title_from(session["messages"])
        session["updated"] = _now_iso()
        self.save()

    # ─── Oturum İşlemleri ───

    def new_session(self) -> str:
        """Yeni boş oturum oluşturup aktifler. Aktif oturum zaten boşsa onu yeniden kullanır."""
        current = self._active()
        if not current["messages"]:
            return current["id"]
        session = _make_session()
        self._sessions.append(session)
        self._active_id = session["id"]
        self.save()
        return session["id"]

    def switch(self, session_id: str) -> list[dict]:
        """Aktif oturumu değiştirir ve mesajlarının kopyasını döndürür."""
        if any(s["id"] == session_id for s in self._sessions):
            self._active_id = session_id
            self.save()
        return self.active_messages()

    def delete(self, session_id: str) -> None:
        """Oturumu siler; aktif silindiyse en son güncelleneni aktifler."""
        self._sessions = [s for s in self._sessions if s["id"] != session_id]
        if not self._sessions:
            self._sessions = [_make_session()]
        if self._active_id == session_id or self._active_id not in {s["id"] for s in self._sessions}:
            self._active_id = self._latest_id()
        self.save()

    def list_meta(self) -> list[dict]:
        """Kenar çubuğu için oturum özetleri (en yeni üstte)."""
        ordered = sorted(self._sessions, key=lambda s: s.get("updated", ""), reverse=True)
        return [
            {"id": s["id"], "title": s.get("title", _DEFAULT_TITLE), "active": s["id"] == self._active_id}
            for s in ordered
        ]

    def _latest_id(self) -> Optional[str]:
        if not self._sessions:
            return None
        return max(self._sessions, key=lambda s: s.get("updated", ""))["id"]
