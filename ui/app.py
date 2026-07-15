"""
Main GUI for Katip (PyQt6).
Widget tabanlı mesaj balonları, çoklu sohbet oturumları, streaming,
karşılama ekranı ve Windows koyu başlık çubuğu.
"""
import os
import re
import sys
import ctypes
import random
import datetime
import logging
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QSizePolicy, QLineEdit,
    QListWidget, QListWidgetItem, QMenu
)
from PyQt6.QtCore import Qt, QTimer, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor

import markdown

from ui.styles import GLOBAL_STYLE
from ui.worker import AssistantWorker
from ui.chat_view import ChatView, MessageBubble
from ui import icons
from core.config import COLORS, APP_NAME, APP_TAGLINE, WELCOME_SUGGESTIONS, DOWNLOAD_DIR
from core.sessions import SessionStore

logger = logging.getLogger(__name__)


# ─── HTML Sanitizasyonu (model çıktısı için) ───

# downloads klasörünün file:// URL öneki (indirme kartı linkleri için beyaz liste)
_DOWNLOADS_URL_PREFIX = (
    "file:///" + os.path.abspath(DOWNLOAD_DIR).replace(os.sep, "/").replace(" ", "%20")
).lower() + "/"

_DANGEROUS_TAGS = re.compile(
    r"(?is)<(script|iframe|object|embed|link|meta|style)\b.*?(?:</\1\s*>|/?>)"
)
_IMG_TAGS = re.compile(r"(?i)<img\b[^>]*>")
_HREF_ATTR = re.compile(r"""(?is)href\s*=\s*(?P<q>["'])(?P<url>.*?)(?P=q)""")


def _sanitize_model_html(html_text: str) -> str:
    """
    Model çıktısından türeyen HTML'i güvenli hale getirir (derinlemesine savunma):
    - script/iframe/img vb. etiketler kaldırılır,
    - linkler yalnızca http(s) ve downloads klasörü içi file:// olabilir.
    Böylece prompt-injection ile üretilmiş bir link, yerel dosya çalıştıramaz.
    """
    html_text = _DANGEROUS_TAGS.sub("", html_text)
    html_text = _IMG_TAGS.sub("", html_text)

    def _filter_href(m: re.Match) -> str:
        url = m.group("url").strip()
        low = url.lower()
        if low.startswith(("http://", "https://")):
            return f'href="{url}"'
        if low.startswith("file:///") and low.startswith(_DOWNLOADS_URL_PREFIX):
            return f'href="{url}"'
        return 'href="#"'  # diğer tüm şemalar etkisizleştirilir

    return _HREF_ATTR.sub(_filter_href, html_text)


# ─── Markdown → HTML Dönüştürücü ───

def _markdown_to_html(text: str) -> str:
    """
    Standart `markdown` modülünü kullanarak metni HTML'e çevirir.
    'başarıyla ... klasörüne indirildi' metinlerini tıklanabilir dosya kartına dönüştürür.
    """
    html_text = markdown.markdown(text, extensions=['fenced_code', 'nl2br', 'tables'])

    # Dosya indirme tespiti: "✅ 'dosya.pdf' ... başarıyla '<klasör>' klasörüne indirildi."
    match = re.search(r"✅\s+'([^']+)'(?:.*)\s+başarıyla\s+'([^']+)'\s+klasörüne\s+indirildi\.", text)
    if match:
        filename = match.group(1)
        folder = match.group(2)
        filepath = os.path.join(folder, filename)
        file_url = f"file:///{filepath.replace(os.sep, '/').replace(' ', '%20')}"

        card_html = f"""
        <table cellspacing="0" cellpadding="12" style="background-color: {COLORS['bg_card']}; border-left: 3px solid {COLORS['accent_indigo']}; margin-top: 8px; margin-bottom: 8px;">
            <tr>
            <td valign="middle"><span style="font-size: 22px;">📄</span>&nbsp;&nbsp;</td>
            <td valign="middle">
                <span style="color: {COLORS['text_primary']}; font-weight: 700; font-size: 14px;">{filename}</span><br>
                <a href="{file_url}" style="color: {COLORS['accent_indigo']}; text-decoration: none; font-size: 13px;">Açmak için tıkla ↗</a>
            </td>
            </tr>
        </table>
        """
        pattern = r"✅\s+'{0}'(?:\s*(?:<[^>]+>\s*)*.*)\s+başarıyla\s+'{1}'\s+klasörüne\s+indirildi\.".format(
            re.escape(filename), re.escape(folder)
        )
        html_text = re.sub(pattern, card_html, html_text)

    # Kod blokları için inline stil (Qt zengin metin motoru harici CSS yüklemez)
    html_text = html_text.replace(
        "<pre>",
        "<pre style=\"background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px;"
        " font-family: Consolas, monospace; font-size: 13px; color: #e2e8f0;\">"
    )
    html_text = html_text.replace(
        "<code>",
        "<code style=\"background: rgba(0,0,0,0.25); padding: 2px 5px; border-radius: 3px;"
        " font-family: Consolas, monospace;\">"
    )
    return _sanitize_model_html(html_text)


def _enable_dark_title_bar(window: QWidget) -> None:
    """Windows'ta pencere başlık çubuğunu koyu moda alır (desteklenmiyorsa sessizce geçer)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(window.winId())
        value = ctypes.c_int(1)
        # 20 = DWMWA_USE_IMMERSIVE_DARK_MODE (Win10 20H1+), 19 = eski build'ler
        for attribute in (20, 19):
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
    except Exception:
        logger.debug("Koyu başlık çubuğu uygulanamadı.", exc_info=True)


class VoiceVisualizer(QWidget):
    """Hareketli ses dalgaları çizen widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 40)
        self.bars = [10, 20, 15, 25, 10]
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_bars)

    def start(self):
        self.timer.start(80)
        self.setVisible(True)

    def stop(self):
        self.timer.stop()
        self.setVisible(False)
        self.bars = [10, 10, 10, 10, 10]
        self.update()

    def _update_bars(self):
        self.bars = [random.randint(5, 35) for _ in range(5)]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bar_width = 6
        spacing = 4
        total_width = (5 * bar_width) + (4 * spacing)
        start_x = (self.width() - total_width) / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(COLORS["accent_indigo"]))

        for i, height in enumerate(self.bars):
            x = start_x + i * (bar_width + spacing)
            y = (self.height() - height) / 2
            painter.drawRoundedRect(QRectF(x, y, bar_width, height), 3, 3)


class App(QMainWindow):
    """Katip ana pencere sınıfı."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icons.app_icon())
        self.resize(1000, 700)
        self.setMinimumSize(520, 520)
        self.setStyleSheet(GLOBAL_STYLE)

        self.store = SessionStore()
        self._stream_bubble: Optional[MessageBubble] = None

        self._setup_ui()
        self._setup_worker()
        self._restore_active_session()

        _enable_dark_title_bar(self)

    # ─── UI Kurulumu ───

    def _setup_ui(self) -> None:
        """Tüm arayüz bileşenlerini oluşturur."""
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # 1. Sol yan panel (oturum listesi)
        self.sidebar_frame = self._create_sidebar()
        main_layout.addWidget(self.sidebar_frame)

        # 2. Sağ ana ekran (header + chat + input)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(14)

        right_layout.addWidget(self._create_header())

        self.chat = ChatView(WELCOME_SUGGESTIONS)
        self.chat.suggestion_clicked.connect(self._run_cmd)
        right_layout.addWidget(self.chat, stretch=1)

        right_layout.addLayout(self._create_bottom_bar())

        main_layout.addWidget(right_panel, stretch=1)

    def _create_sidebar(self) -> QFrame:
        """Sol taraftaki sohbet oturumları paneli."""
        frame = QFrame()
        frame.setObjectName("sidebarFrame")
        frame.setFixedWidth(230)

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 16, 14, 16)
        layout.setSpacing(10)

        title = QLabel("SOHBETLER")
        title.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600;"
            " letter-spacing: 2px; margin-left: 6px; background: transparent;"
        )
        layout.addWidget(title)

        self.new_chat_btn = QPushButton("  Yeni sohbet")
        self.new_chat_btn.setObjectName("newChatBtn")
        self.new_chat_btn.setIcon(icons.svg_icon("plus", COLORS["accent_indigo"], 16))
        self.new_chat_btn.setIconSize(QSize(16, 16))
        self.new_chat_btn.setMinimumHeight(40)
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.clicked.connect(self._new_chat)
        layout.addWidget(self.new_chat_btn)

        layout.addSpacing(4)

        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_list.itemClicked.connect(self._on_session_clicked)
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._session_context_menu)
        layout.addWidget(self.history_list)

        return frame

    def _create_header(self) -> QFrame:
        """Logo + başlık alanı."""
        frame = QFrame()
        frame.setObjectName("headerFrame")

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(30))
        logo.setStyleSheet("background: transparent;")
        layout.addWidget(logo)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title = QLabel(APP_NAME)
        title.setObjectName("headerTitle")
        text_col.addWidget(title)

        subtitle = QLabel(APP_TAGLINE)
        subtitle.setObjectName("headerSubtitle")
        text_col.addWidget(subtitle)

        layout.addLayout(text_col)
        layout.addStretch()

        return frame

    def _create_bottom_bar(self) -> QVBoxLayout:
        """Alt bölüm: metin girişi, gönder/konuş/iptal butonları, durum etiketi."""
        vlayout = QVBoxLayout()
        vlayout.setSpacing(10)

        input_layout = QHBoxLayout()
        input_layout.setSpacing(12)

        self.text_input = QLineEdit()
        self.text_input.setObjectName("textInput")
        self.text_input.setPlaceholderText("Mesajınızı yazın…")
        self.text_input.setFixedHeight(52)
        self.text_input.returnPressed.connect(self._send_text_message)
        input_layout.addWidget(self.text_input)

        self.send_btn = QPushButton("  Gönder")
        self.send_btn.setObjectName("sendBtn")
        self.send_btn.setIcon(icons.svg_icon("send", "#0a0d14", 17))
        self.send_btn.setIconSize(QSize(17, 17))
        self.send_btn.setFixedSize(130, 52)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self._send_text_message)
        input_layout.addWidget(self.send_btn)

        self.mic_btn = QPushButton("  Konuş")
        self.mic_btn.setObjectName("micBtn")
        self.mic_btn.setIcon(icons.svg_icon("mic", COLORS["accent_indigo"], 17))
        self.mic_btn.setIconSize(QSize(17, 17))
        self.mic_btn.setFixedSize(130, 52)
        self.mic_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mic_btn.clicked.connect(self._start_listening)
        input_layout.addWidget(self.mic_btn)

        # Ses animasyonu widget'ı
        self.visualizer = VoiceVisualizer()
        self.visualizer.setVisible(False)
        input_layout.addWidget(self.visualizer)

        # İptal butonu (varsayılan gizli)
        self.cancel_btn = QPushButton("  İptal")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setIcon(icons.svg_icon("x", "#ffffff", 17))
        self.cancel_btn.setIconSize(QSize(17, 17))
        self.cancel_btn.setFixedSize(130, 52)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_operation)
        self.cancel_btn.setVisible(False)
        input_layout.addWidget(self.cancel_btn)

        vlayout.addLayout(input_layout)

        self.status_label = QLabel("Hazır")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        vlayout.addWidget(self.status_label)

        return vlayout

    # ─── Worker ───

    def _setup_worker(self) -> None:
        """AssistantWorker thread'ini hazırlar ve sinyalleri bağlar."""
        self.worker = AssistantWorker(store=self.store)
        self.worker.status_signal.connect(self._update_status)
        self.worker.chat_signal.connect(self._update_chat)
        self.worker.finished_signal.connect(self._on_worker_finished)

        # Streaming sinyalleri
        self.worker.stream_start_signal.connect(self._on_stream_start)
        self.worker.stream_signal.connect(self._on_stream_token)
        self.worker.stream_end_signal.connect(self._on_stream_end)

    # ─── Oturum Yönetimi ───

    def _restore_active_session(self) -> None:
        """Açılışta son aktif oturumu hem worker'a hem ekrana yükler."""
        messages = self.store.active_messages()
        self.worker.chat_session = messages
        self._render_messages(messages)
        self._refresh_sidebar()

    def _render_messages(self, messages: list[dict]) -> None:
        """Oturum mesajlarını sohbet ekranına çizer (gizli/araç mesajları atlanır)."""
        self.chat.clear()
        for msg in messages:
            role = msg.get("role")
            content = (msg.get("content") or "").strip()
            ts = msg.get("ts", "")

            if not content or role == "system" or msg.get("hidden"):
                continue
            # Eski formattan kalan araç mesajlarını da filtrele
            if role == "user" and content.startswith("ARAÇ_SONUCU"):
                continue
            if role == "assistant" and "OLLAMA_TOOL:" in content:
                continue

            if role == "user":
                bubble = self.chat.add_bubble("Siz", True, ts)
                bubble.set_plain(content)
            elif role == "assistant":
                bubble = self.chat.add_bubble("Asistan", False, ts)
                bubble.set_rich(_markdown_to_html(content), content)

    def _refresh_sidebar(self) -> None:
        """Kenar çubuğunu oturum listesiyle yeniden doldurur."""
        self.history_list.clear()
        for meta in self.store.list_meta():
            item = QListWidgetItem(meta["title"])
            item.setData(Qt.ItemDataRole.UserRole, meta["id"])
            self.history_list.addItem(item)
            if meta["active"]:
                item.setSelected(True)

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        """Kenar çubuğundan oturum seçimi."""
        if self.worker.isRunning():
            self._update_status("Yanıt tamamlanmadan oturum değiştirilemez")
            return
        session_id = item.data(Qt.ItemDataRole.UserRole)
        if session_id == self.store.active_id:
            return
        messages = self.store.switch(session_id)
        self.worker.chat_session = messages
        self._render_messages(messages)
        self._refresh_sidebar()
        self._update_status("Hazır")

    def _session_context_menu(self, pos) -> None:
        """Oturum öğesine sağ tık menüsü (silme)."""
        item = self.history_list.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction(
            icons.svg_icon("trash", COLORS["accent_rose"], 14), "Sohbeti sil"
        )
        chosen = menu.exec(self.history_list.mapToGlobal(pos))
        if chosen is delete_action:
            self._delete_session(item.data(Qt.ItemDataRole.UserRole))

    def _delete_session(self, session_id: str) -> None:
        if self.worker.isRunning():
            self._update_status("Yanıt tamamlanmadan oturum silinemez")
            return
        was_active = session_id == self.store.active_id
        self.store.delete(session_id)
        if was_active:
            messages = self.store.active_messages()
            self.worker.chat_session = messages
            self._render_messages(messages)
        self._refresh_sidebar()
        self._update_status("Sohbet silindi")

    def _new_chat(self) -> None:
        """Yeni boş sohbet oturumu başlatır."""
        if self.worker.isRunning():
            self._update_status("Yanıt tamamlanmadan yeni sohbet açılamaz")
            return
        self.store.new_session()
        self.worker.chat_session = []
        self.chat.clear()
        self._refresh_sidebar()
        self._update_status("Yeni sohbet")

    # ─── Aksiyon Yönetimi ───

    def _send_text_message(self) -> None:
        """Metin alanındaki komutu arka planda çalıştırır."""
        text = self.text_input.text().strip()
        if not text:
            self._update_status("Lütfen bir mesaj yazın")
            return
        if not self.worker.isRunning():
            self.text_input.clear()
            self._run_cmd(text)

    def _run_cmd(self, cmd: str) -> None:
        if not self.worker.isRunning():
            self._set_working_mode(True)
            self.worker.manual_command = cmd
            self.worker.start()

    def _start_listening(self) -> None:
        if not self.worker.isRunning():
            self._set_working_mode(True)
            self.visualizer.start()
            self.worker.start()

    def _cancel_operation(self) -> None:
        """Devam eden işlemi iptal eder."""
        self.worker.cancel()
        self._update_status("İptal ediliyor…")

    def _on_worker_finished(self) -> None:
        self._set_working_mode(False)
        self.visualizer.stop()
        self._refresh_sidebar()

    def _set_working_mode(self, working: bool) -> None:
        """Çalışma modundayken butonları değiştirir."""
        self.mic_btn.setEnabled(not working)
        self.send_btn.setEnabled(not working)
        self.text_input.setEnabled(not working)
        self.new_chat_btn.setEnabled(not working)
        self.mic_btn.setVisible(not working)
        self.send_btn.setVisible(not working)
        self.cancel_btn.setVisible(working)

    # ─── Streaming Yönetimi ───

    def _on_stream_start(self) -> None:
        """Streaming başladığında boş asistan balonu hazırlar."""
        ts = datetime.datetime.now().strftime("%H:%M")
        self._stream_bubble = self.chat.add_bubble("Asistan", False, ts)

    def _on_stream_token(self, token: str) -> None:
        """Gelen her token'ı streaming balonuna ekler."""
        if self._stream_bubble is not None:
            self._stream_bubble.stream_append(token.replace("\r", ""))

    def _on_stream_end(self) -> None:
        """Streaming bitti — imleci kaldır (nihai render chat_signal ile gelir)."""
        if self._stream_bubble is not None:
            self._stream_bubble.finish_stream()

    # ─── Arayüz Güncelleyiciler ───

    def _update_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _update_chat(self, gonderen: str, mesaj: str) -> None:
        """Chat ekranına yeni mesaj ekler (asistan mesajları markdown render edilir)."""
        ts = datetime.datetime.now().strftime("%H:%M")

        if gonderen == "Siz":
            bubble = self.chat.add_bubble("Siz", True, ts)
            bubble.set_plain(mesaj)
            return

        # Asistan: streaming balonu varsa onu nihai içerikle güncelle
        if self._stream_bubble is not None:
            bubble = self._stream_bubble
            self._stream_bubble = None
        else:
            bubble = self.chat.add_bubble("Asistan", False, ts)
        bubble.set_rich(_markdown_to_html(mesaj), mesaj)
