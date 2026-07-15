"""
Background worker handling speech recognition and Ollama AI integration.
Supports streaming responses, cancellation, and tool execution.
"""
import os
import re
import json
import tempfile
import datetime
import logging
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal
import sounddevice as sd
from scipy.io import wavfile
import speech_recognition as sr
import ollama

from core.config import (
    APP_NAME, MODEL_NAME, OLLAMA_BASE_URL, OLLAMA_TIMEOUT,
    MAX_HISTORY_LENGTH, LISTEN_DURATION_SECONDS, LISTEN_SAMPLE_RATE,
    MAX_TOOL_ITERATIONS, MAX_RETRIES
)
from core import tools
from core.sessions import SessionStore

logger = logging.getLogger(__name__)

# ─── Ollama İstemcisi ───
# Not: ollama.chat() global fonksiyonu OLLAMA_HOST ortam değişkenini okur; yapılandırdığımız
# OLLAMA_BASE_URL'i dikkate almaz. Bu yüzden host'u açıkça veren bir Client kullanıyoruz.
_ollama_client = ollama.Client(host=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT)

# ─── Araç JSON çıkarıcı (regex tabanlı) ───
_TOOL_PATTERN = re.compile(r'OLLAMA_TOOL:\s*(\{.*\})', re.DOTALL | re.IGNORECASE)


class AssistantWorker(QThread):
    """Ses dinleme ve AI yanıt alma işlemlerini arka planda yürütür."""

    status_signal = pyqtSignal(str)
    chat_signal = pyqtSignal(str, str)          # (sender, full_message)
    stream_signal = pyqtSignal(str)             # chunk — streaming token
    stream_start_signal = pyqtSignal()          # streaming başladı
    stream_end_signal = pyqtSignal()            # streaming bitti
    finished_signal = pyqtSignal()

    # Not: 'gmail_mail_gonder' bilinçli olarak yok — uygulama e-posta gönderemez,
    # yalnızca okuyabilir.
    AVAILABLE_TOOLS = {
        'gmail_son_mailleri_getir': tools.gmail_son_mailleri_getir,
        'takvim_etkinlik_ekle': tools.takvim_etkinlik_ekle,
        'takvim_etkinlikleri_getir': tools.takvim_etkinlikleri_getir,
        'drive_listele': tools.drive_listele,
        'drive_dosya_indir': tools.drive_dosya_indir,
        'docs_belge_olustur': tools.docs_belge_olustur,
        'yerel_dosya_oku': tools.yerel_dosya_oku,
    }

    def __init__(self, store: Optional[SessionStore] = None) -> None:
        super().__init__()
        self.manual_command: Optional[str] = None
        self.chat_session: list[dict] = []
        self.store = store
        self._cancelled: bool = False

    # ─── İptal Mekanizması ───

    def cancel(self) -> None:
        """Devam eden işlemi iptal eder."""
        self._cancelled = True
        logger.info("İşlem iptal edildi.")

    def _is_cancelled(self) -> bool:
        """İptal durumunu kontrol eder."""
        return self._cancelled

    # ─── Geçmiş Yönetimi ───

    def _persist(self) -> None:
        """Aktif oturumu depoya yazar (store, App tarafından atanır)."""
        if self.store is None:
            return
        try:
            self.store.set_active_messages(self.chat_session)
        except Exception as e:
            logger.error("Oturum kaydedilirken hata: %s", e)

    def _trim_history(self) -> None:
        """Geçmişi MAX_HISTORY_LENGTH mesajla sınırlar (system prompt hariç)."""
        if len(self.chat_session) <= 1:
            return
        system_msg = self.chat_session[0] if self.chat_session[0].get("role") == "system" else None
        messages = self.chat_session[1:] if system_msg else self.chat_session

        if len(messages) > MAX_HISTORY_LENGTH:
            trimmed = messages[-MAX_HISTORY_LENGTH:]
            self.chat_session = ([system_msg] if system_msg else []) + trimmed

    def _ensure_system_note(self, sistem_notu: str) -> None:
        """System prompt'u ekler ya da günceller (tarih/saat her turda taze kalır)."""
        if not self.chat_session or self.chat_session[0].get("role") != "system":
            self.chat_session.insert(0, {"role": "system", "content": sistem_notu})
        else:
            self.chat_session[0]["content"] = sistem_notu

    # ─── Thread Çalıştırıcı ───

    def run(self) -> None:
        """Thread'i çalıştırır: ses dinler ya da manuel komutu işler."""
        self._cancelled = False
        try:
            if self.manual_command:
                user_input = self.manual_command
                self.manual_command = None
            else:
                self.status_signal.emit("Dinleniyor…")
                user_input = self._dinle()

            if self._is_cancelled():
                self.status_signal.emit("İptal edildi")
                return

            if user_input:
                self.chat_signal.emit("Siz", user_input)
                self.status_signal.emit("Düşünüyor…")
                yanit = self._asistana_sor(user_input)

                if self._is_cancelled():
                    self.status_signal.emit("İptal edildi")
                    return

                if yanit:
                    self.chat_signal.emit("Asistan", yanit)

            self.status_signal.emit("Hazır")
        except Exception as e:
            logger.error("Worker hatası: %s", e)
            self.status_signal.emit("Hata oluştu")
        finally:
            self.finished_signal.emit()

    # ─── Ses Dinleme ───

    def _dinle(self) -> Optional[str]:
        """Mikrofonu dinler, sesi yazıya çevirir."""
        tmp_fd = None
        tmp_path = None
        try:
            # Güvenli geçici dosya oluştur
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.wav', prefix='asst_')
            os.close(tmp_fd)
            tmp_fd = None

            kayit = sd.rec(
                int(LISTEN_DURATION_SECONDS * LISTEN_SAMPLE_RATE),
                samplerate=LISTEN_SAMPLE_RATE, channels=1, dtype='int16'
            )
            sd.wait()

            if self._is_cancelled():
                return None

            wavfile.write(tmp_path, LISTEN_SAMPLE_RATE, kayit)
            r = sr.Recognizer()
            with sr.AudioFile(tmp_path) as src:
                audio = r.record(src)
                return r.recognize_google(audio, language='tr-TR').lower()
        except sr.UnknownValueError:
            self.status_signal.emit("Ses anlaşılamadı, tekrar deneyin")
            logger.info("Ses algılandı ama anlaşılamadı.")
            return None
        except sr.RequestError as e:
            self.status_signal.emit("Ses tanıma servisi hatası")
            logger.error("Google Speech API hatası: %s", e)
            return None
        except Exception as e:
            self.status_signal.emit("Mikrofon hatası")
            logger.error("Ses dinleme hatası: %s", e)
            return None
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ─── Araç Çağrısı ───

    def _parse_and_execute_tool(self, content: str) -> str:
        """Metindeki OLLAMA_TOOL formatını regex ile ayrıştırıp çalıştırır."""
        try:
            match = _TOOL_PATTERN.search(content)
            if not match:
                return "Hata: OLLAMA_TOOL JSON formatı bulunamadı."

            json_str = match.group(1).strip()
            if json_str.startswith("```"):
                json_str = re.sub(r'^```\w*\n?', '', json_str)
            if json_str.endswith("```"):
                json_str = json_str[:-3].strip()

            tool_call = json.loads(json_str)
            func_name = tool_call["name"]
            func_args = tool_call.get("args", {})

            logger.info("Araç çağrılıyor -> %s(%s)", func_name, func_args)
            self.status_signal.emit(f"{func_name} çalıştırılıyor…")

            if func_name in self.AVAILABLE_TOOLS:
                return str(self.AVAILABLE_TOOLS[func_name](**func_args))
            else:
                available = ", ".join(self.AVAILABLE_TOOLS.keys())
                return f"Hata: '{func_name}' adında bir araç bulunamadı. Kullanılabilir araçlar: {available}"
        except json.JSONDecodeError as e:
            logger.error("JSON parse hatası: %s", e)
            return f"Hata: Araç JSON'u okunamadı: {e}"
        except TypeError as e:
            logger.error("Araç parametre hatası: %s", e)
            return f"Hata: Araç parametreleri hatalı: {e}"
        except Exception as e:
            logger.error("Araç çalıştırma hatası: %s", e)
            return f"Hata: Araç çalıştırılamadı: {e}"

    # ─── AI İletişimi (Streaming) ───

    # Tool çağrısı tespiti için yeterli karakter sayısı
    _TOOL_DETECT_THRESHOLD = 30

    def _stream_chat(self, messages: list[dict], deferred: bool = False) -> str:
        """
        Ollama'ya streaming chat isteği gönderir.

        deferred=True ise ilk token'lar biriktirilir ve OLLAMA_TOOL
        tespiti yapılır. Tool çağrısı değilse biriken token'lar UI'a
        gönderilir ve normal streaming'e devam edilir.
        Tool çağrısıysa hiçbir token UI'a gönderilmez.

        deferred=False ise her token doğrudan UI'a iletilir.

        Args:
            messages: Sohbet mesaj listesi.
            deferred: True ise araç çağrısı kontrolü için ertelemeli mod.

        Returns:
            str: Tamamlanmış yanıt metni.
        """
        full_content: str = ""
        is_tool_call: bool = False
        stream_started: bool = False
        buffer: str = ""

        if not deferred:
            self.stream_start_signal.emit()
            stream_started = True

        try:
            # Ollama'ya yalnızca role/content gönder ("ts" gibi yerel alanları ayıkla)
            wire_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
            stream = _ollama_client.chat(
                model=MODEL_NAME,
                messages=wire_messages,
                stream=True
            )
            for chunk in stream:
                if self._is_cancelled():
                    break
                
                content_val = chunk.get('message', {}).get('content', '')
                token = str(content_val) if content_val else ""
                
                if token:
                    full_content += token

                    if deferred and not stream_started:
                        # Biriktirme aşaması
                        buffer += token

                        if "OLLAMA_TOOL" in buffer:
                            # Tool çağrısı tespit edildi — UI'a hiçbir şey gönderme
                            is_tool_call = True
                            continue

                        if len(buffer) >= self._TOOL_DETECT_THRESHOLD:
                            # Yeterli karakter birikti, tool değil — streaming başlat
                            self.stream_start_signal.emit()
                            stream_started = True
                            self.stream_signal.emit(buffer)
                            buffer = ""
                    elif not is_tool_call and stream_started:
                        self.stream_signal.emit(token)

            # Deferred modda buffer kaldıysa ve tool değilse, son kısmı flush et
            if deferred and buffer and not is_tool_call and not stream_started:
                self.stream_start_signal.emit()
                stream_started = True
                self.stream_signal.emit(buffer)
        finally:
            if stream_started:
                self.stream_end_signal.emit()

        return full_content.strip()

    def _asistana_sor(self, komut: str) -> str:
        """Ollama modeline soruyu yönlendirir ve sohbet geçmişini korur."""
        bugun_str = datetime.datetime.now().strftime("%Y-%m-%d")
        saat_str = datetime.datetime.now().strftime("%H:%M")
        gun_str = datetime.datetime.now().strftime("%A")
        
        sistem_notu = f"""Sen {APP_NAME} adında yetenekli ve profesyonel bir asistansın.
Bugünün Tarihi: {bugun_str} ({gun_str}), Saat: {saat_str}, Saat Dilimi: Europe/Istanbul.

Kullanıcının isteğini yerine getir. Eğer isteği doğrudan cevaplayabiliyorsan, sadece doğal bir dille yanıt ver.
EĞER YARDIMCI BİR ARACA İHTİYACIN VARSA, cevabını SADECE aşağıdaki JSON formatında vermelisin ve DIŞINA HİÇBİR METİN VEYA AÇIKLAMA YAZMAMALISIN. Araç çıktısı haricinde hiçbir yorum yapma.
OLLAMA_TOOL: {{"name": "aracin_adi", "args": {{"parametre1": "deger1", "parametre2": 3}}}}

Kullanabileceğin Araçlar:
1. gmail_son_mailleri_getir(limit: int, sorgu: str): Son e-postaları getirir veya 'sorgu' ile arama yapar (Örn: "from:ahmet" veya "fatura").
2. takvim_etkinlik_ekle(baslik: str, baslangic_zamani: str, bitis_zamani: str, aciklama: str): Takvime etkinlik ekler. Zaman FORMATI YYYY-MM-DDTHH:MM:SS olmalıdır. 'bitis_zamani' ve 'aciklama' isteğe bağlıdır. Bugünün tarihini ({bugun_str}) referans al.
3. takvim_etkinlikleri_getir(limit: int): Gelecekteki takvim etkinliklerini listeler.
4. drive_listele(sorgu: str): Google Drive'daki dosyaları listeler. İsteğe bağlı olarak 'sorgu' ile arama yapabilirsin (Örn: "name contains 'Fatura'").
5. drive_dosya_indir(dosya_adi: str): Drive'dan tam veya kısmi dosya adıyla indirme yapar. (Hata alırsan önce listelemeyi dene).
6. docs_belge_olustur(baslik: str, icerik: str): Yeni Google Docs belgesi oluşturur.
7. yerel_dosya_oku(dosya_adi: str): Yerel klasöre indirilmiş belgeleri (PDF, DOCX, TXT) okur. ('dosya_adi' parametresini tam gir).

ÖNEMLİ KURALLAR:
- Çıktı KESİNLİKLE sadece yukarıdaki JSON formatında olmalı. "Elbette...", "İşte..." gibi giriş cümleleri KULLANMA.
- JSON içindeki değerler string ise çift tırnak (") ile sarılmalıdır.
- "Yarın", "Haftaya" gibi ifadeleri referans tarihe ({bugun_str}) göre hesaplayarak ISO formatına çevir.
- E-POSTA GÖNDEREMEZSİN. Sadece okuyabilirsin. Kullanıcı mail göndermeni isterse, bunu yapamayacağını kibarca açıkla.
- Eğer bir araç hata verirse farklı parametrelerle tekrar deneyebilirsin veya kullanıcıya bu durumu açıklayabilirsin."""

        self._ensure_system_note(sistem_notu)
        self.chat_session.append({"role": "user", "content": komut, "ts": saat_str})
        self._trim_history()

        # ─── Bağlantı hatasına karşı tekrar deneme döngüsü ───
        son_hata = ""
        for deneme in range(MAX_RETRIES):
            if self._is_cancelled():
                return ""
            try:
                logger.info("Mesaj gönderiliyor (deneme %d/%d)", deneme + 1, MAX_RETRIES)
                return self._agentic_loop()
            except Exception as e:
                son_hata = str(e)
                logger.error("Chat gönderim hatası: %s", e)
                bekleme = 2 * (deneme + 1)
                self.status_signal.emit(f"Bağlantı hatası, {bekleme} sn sonra yeniden denenecek…")
                self.msleep(bekleme * 1000)  # QThread uyuması (time.sleep yerine)
                continue

        return self._friendly_connection_error(son_hata)

    def _agentic_loop(self) -> str:
        """
        Asistanı çok turlu (agentic) çalıştırır: model bir araç çağırdıkça sonucu
        geçmişe ekler ve modele tekrar sorar. Model artık araç çağırmadığında nihai
        metni döndürür. Böylece "önce listele, sonra indir" gibi zincirleme görevler
        tek komutta tamamlanabilir.

        Tüm istekler 'deferred' modda yapılır; araç çağrısı JSON'u asla kullanıcıya
        sızmaz, normal yanıtlar ise canlı stream edilir.
        """
        for tur in range(MAX_TOOL_ITERATIONS):
            if self._is_cancelled():
                return ""

            content = self._stream_chat(self.chat_session, deferred=True)

            if self._is_cancelled():
                return ""

            # Araç çağrısı yoksa: bu, kullanıcıya gösterilen nihai yanıttır.
            if "OLLAMA_TOOL:" not in content:
                ts = datetime.datetime.now().strftime("%H:%M")
                self.chat_session.append({"role": "assistant", "content": content, "ts": ts})
                self._trim_history()
                self._persist()
                return content

            # Araç çağrısı: çalıştır, sonucu geçmişe ekle, döngüye devam et.
            logger.info("Asistan araç çağırıyor (tur %d/%d)...", tur + 1, MAX_TOOL_ITERATIONS)
            tool_result = self._parse_and_execute_tool(content)
            logger.info("Araç sonucu: %s", tool_result)

            self.chat_session.append({"role": "assistant", "content": content, "hidden": True})
            self.chat_session.append({
                "role": "user",
                "content": (
                    f"ARAÇ_SONUCU:\n{tool_result}\n\n"
                    "ÖNEMLİ: Kullanıcı bu araç sonucunu göremiyor. Görevi tamamlamak için başka "
                    "bir araca ihtiyacın varsa yeni bir OLLAMA_TOOL çağrısı yap; aksi halde yukarıdaki "
                    "bilgileri kullanıcıya doğrudan, eksiksiz ve doğal bir dille sun."
                ),
                "hidden": True
            })
            self.status_signal.emit("Sonuç değerlendiriliyor…")

        # Maksimum araç turuna ulaşıldı → araçsız bir nihai özet iste (sonsuz döngü koruması).
        logger.warning("Maksimum araç turu (%d) aşıldı, özet isteniyor.", MAX_TOOL_ITERATIONS)
        self.chat_session.append({
            "role": "user",
            "content": (
                "Maksimum araç sayısına ulaşıldı. Başka araç ÇAĞIRMA. "
                "Şu ana kadar topladığın bilgilerle kullanıcıya doğrudan yanıt ver."
            ),
            "hidden": True
        })
        final_content = self._stream_chat(self.chat_session, deferred=True)
        ts = datetime.datetime.now().strftime("%H:%M")
        self.chat_session.append({"role": "assistant", "content": final_content, "ts": ts})
        self._trim_history()
        self._persist()
        return final_content

    @staticmethod
    def _friendly_connection_error(detail: str) -> str:
        """Ham bağlantı hatasını kullanıcı için anlaşılır, aksiyon alınabilir bir mesaja çevirir."""
        low = detail.lower()
        if any(k in low for k in ("not found", "no such model", "try pulling")):
            return (
                f"⚠️ '{MODEL_NAME}' modeli Ollama'da bulunamadı.\n"
                f"Lütfen şu komutla indirin:  ollama pull {MODEL_NAME}"
            )
        if any(k in low for k in ("connection", "refused", "max retries", "timed out", "timeout", "connect")):
            return (
                "⚠️ Ollama sunucusuna ulaşılamıyor.\n"
                f"Çalıştığından emin olun (ollama serve) ve adresi kontrol edin: {OLLAMA_BASE_URL}"
            )
        return (
            "⚠️ Asistana şu anda ulaşılamıyor.\n"
            "Lütfen biraz bekleyip tekrar deneyin.\n"
            f"Detay: {detail}"
        )
