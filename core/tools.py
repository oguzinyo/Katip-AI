"""
Google API Tools (Gmail, Calendar, Drive, Docs) for the Assistant.
Includes service caching, error handling, and security hardening.
"""
import base64
import io
import os
import re
import html as html_module
import datetime
import logging

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx
except ImportError:
    docx = None

from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from core.auth import get_google_creds
from core.config import (
    DOWNLOAD_DIR, MAX_DOWNLOAD_SIZE_MB,
    FILE_READ_CHAR_LIMIT, GMAIL_BODY_CHAR_LIMIT,
)

logger = logging.getLogger(__name__)


# ─── Service Caching ───

_service_cache: dict[str, Resource] = {}


def _get_service(api: str, version: str) -> Resource:
    """
    Google API servis nesnesini cache'den döndürür.
    Aynı API için tekrar tekrar build() çağırmak yerine singleton kullanır.

    Args:
        api: API adı (ör: 'gmail', 'calendar', 'drive', 'docs')
        version: API versiyonu (ör: 'v1', 'v3')

    Returns:
        Resource: Hazır Google API servis nesnesi.
    """
    key = f"{api}:{version}"
    if key not in _service_cache:
        logger.info("API servisi oluşturuluyor: %s %s", api, version)
        _service_cache[key] = build(api, version, credentials=get_google_creds())
    return _service_cache[key]


def clear_service_cache() -> None:
    """Servis cache'ini temizler (credential yenilendiğinde çağrılır)."""
    _service_cache.clear()
    logger.info("API servis cache'i temizlendi.")


def _sanitize_query(value: str) -> str:
    """Drive arama sorgularında özel karakterleri escape eder."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


# ─── E-posta Gövdesi Çözümleme ───

def _decode_b64(data: str) -> str:
    """Gmail'in base64url gövdesini güvenle metne çevirir."""
    try:
        return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    except Exception:
        return ""


def _html_to_text(raw_html: str) -> str:
    """Basit HTML→düz metin: script/style atılır, etiketler silinir, boşluk sadeleştirilir."""
    raw_html = re.sub(r'(?is)<(script|style).*?</\1>', ' ', raw_html)
    raw_html = re.sub(r'(?i)<br\s*/?>', '\n', raw_html)
    raw_html = re.sub(r'(?i)</p>', '\n', raw_html)
    text = re.sub(r'<[^>]+>', ' ', raw_html)
    text = html_module.unescape(text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    return text.strip()


def _extract_email_body(payload: dict) -> str:
    """
    E-posta gövdesini çıkarır: önce text/plain bölümleri, yoksa text/html
    (etiketleri temizlenmiş) kullanılır. Çok parçalı (multipart) yapıları gezer.
    """
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def _walk(part: dict) -> None:
        mime = part.get('mimeType', '')
        data = part.get('body', {}).get('data')
        if data:
            if mime == 'text/plain':
                plain_parts.append(_decode_b64(data))
            elif mime == 'text/html':
                html_parts.append(_decode_b64(data))
        for sub in part.get('parts', []):
            _walk(sub)

    _walk(payload)

    plain = "\n".join(p for p in plain_parts if p).strip()
    if plain:
        return plain
    html_joined = "\n".join(h for h in html_parts if h).strip()
    return _html_to_text(html_joined) if html_joined else ""


# ─── Gmail ───

def gmail_son_mailleri_getir(limit: int = 3, sorgu: str = "") -> str:
    """
    Gelen kutusundaki son e-postaları getirir veya belirtilen sorguya göre arama yapar.

    Args:
        limit: Getirilecek e-posta sayısı (varsayılan: 3).
        sorgu: İsteğe bağlı arama sorgusu (ör: 'from:ahmet', 'is:unread').

    Returns:
        str: E-posta konularının özeti veya hata mesajı.
    """
    try:
        service = _get_service('gmail', 'v1')
        kwargs: dict[str, object] = {
            'userId': 'me',
            'maxResults': limit
        }
        if sorgu:
            kwargs['q'] = sorgu
        else:
            kwargs['labelIds'] = ['INBOX']
            
        results = service.users().messages().list(**kwargs).execute()
        messages = results.get('messages', [])
        if not messages:
            return "Hiç e-posta bulunamadı."

        ozet = "📧 Son E-postalarınız:\n"
        for msg in messages:
            m = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            payload = m.get('payload', {})
            headers = payload.get('headers', [])
            
            subj = next((h['value'] for h in headers if h['name'] == 'Subject'), "Konu Yok")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Bilinmeyen")

            body_text = _extract_email_body(payload)
            if not body_text:
                body_text = m.get('snippet', '')

            if len(body_text) > GMAIL_BODY_CHAR_LIMIT:
                body_text = body_text[:GMAIL_BODY_CHAR_LIMIT] + "... (devamı var)"

            body_snippet = body_text.strip()
            if not body_snippet:
                body_snippet = "İçerik okunamadı."
                
            ozet += f"  • **Konu:** {subj}\n    **Kimden:** {sender}\n    **İçerik:**\n{body_snippet}\n\n"

        return ozet
    except HttpError as e:
        logger.error("Gmail API hatası [%s]: %s", e.resp.status, e)
        return f"Gmail API hatası ({e.resp.status}): {e._get_reason()}"
    except Exception as e:
        logger.error("Gmail hatası: %s", e)
        return f"Gmail hatası: {e}"


# Not: E-posta GÖNDERME özelliği bilinçli olarak kaldırıldı. Uygulama yalnızca
# gmail.readonly izniyle çalışır ve e-posta gönderemez.


# ─── Calendar ───

def takvim_etkinlik_ekle(baslik: str, baslangic_zamani: str, bitis_zamani: str = "", aciklama: str = "") -> str:
    """
    Takvime etkinlik ekler.

    Args:
        baslik: Etkinlik başlığı.
        baslangic_zamani: Başlangıç zamanı (format: 2026-02-28T14:00:00).
        bitis_zamani: İsteğe bağlı bitiş zamanı (format: 2026-02-28T15:00:00). Varsayılan süre 1 saattir.
        aciklama: İsteğe bağlı etkinlik açıklaması.

    Returns:
        str: Başarı veya hata mesajı.
    """
    try:
        service = _get_service('calendar', 'v3')
        
        # Clean up timezone artifacts from LLM Output
        clean_time = baslangic_zamani.replace('Z', '').replace('+03:00', '').strip()
        if 'T' not in clean_time and len(clean_time) == 10:
            clean_time += "T09:00:00" # Var sayılan sabah 9
            
        baslangic = datetime.datetime.fromisoformat(clean_time)
        
        if bitis_zamani:
            clean_end = bitis_zamani.replace('Z', '').replace('+03:00', '').strip()
            if 'T' not in clean_end and len(clean_end) == 10:
                clean_end += "T10:00:00"
            bitis = datetime.datetime.fromisoformat(clean_end)
        else:
            bitis = baslangic + datetime.timedelta(hours=1)
            
        event = {
            'summary': baslik,
            'start': {'dateTime': baslangic.isoformat(), 'timeZone': 'Europe/Istanbul'},
            'end':   {'dateTime': bitis.isoformat(),     'timeZone': 'Europe/Istanbul'},
        }
        if aciklama:
            event['description'] = aciklama
            
        service.events().insert(calendarId='primary', body=event).execute()
        return f"✅ '{baslik}' takvime eklendi ({baslangic.strftime('%H:%M')} – {bitis.strftime('%H:%M')})."
    except ValueError:
        return "❌ Tarih formatı hatalı. Doğru format: 2026-02-28T14:00:00"
    except HttpError as e:
        logger.error("Takvim API hatası [%s]: %s", e.resp.status, e)
        return f"Takvim hatası ({e.resp.status}): {e._get_reason()}"
    except Exception as e:
        logger.error("Takvim hatası: %s", e)
        return f"Takvim hatası: {e}"


def takvim_etkinlikleri_getir(limit: int = 5) -> str:
    """
    Bugünden itibaren yaklaşan takvim etkinliklerini listeler.

    Args:
        limit: Getirilecek etkinlik sayısı (varsayılan: 5).

    Returns:
        str: Etkinlik listesi veya hata mesajı.
    """
    try:
        service = _get_service('calendar', 'v3')
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=limit,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return "📅 Yaklaşan etkinlik bulunamadı."

        ozet = "📅 Yaklaşan Etkinlikleriniz:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            try:
                dt = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                tarih_str = dt.strftime('%d/%m/%Y %H:%M')
            except (ValueError, AttributeError):
                tarih_str = start

            summary = event.get('summary', 'Başlıksız Etkinlik')
            ozet += f"  • **{summary}** — {tarih_str}\n"
        return ozet
    except HttpError as e:
        logger.error("Takvim listeleme API hatası [%s]: %s", e.resp.status, e)
        return f"Takvim listeleme hatası ({e.resp.status}): {e._get_reason()}"
    except Exception as e:
        logger.error("Takvim listeleme hatası: %s", e)
        return f"Takvim listeleme hatası: {e}"


# ─── Drive ───

def drive_listele(sorgu: str = "") -> str:
    """
    Google Drive'daki dosyaları listeler veya arama yapar.

    Args:
        sorgu: İsteğe bağlı arama sorgusu (ör: "name contains 'Fatura'").

    Returns:
        str: Dosya listesi veya hata mesajı.
    """
    try:
        service = _get_service('drive', 'v3')
        kwargs = {
            'pageSize': 10,
            'fields': "files(id, name, mimeType, modifiedTime)"
        }
        if sorgu:
            kwargs['q'] = sorgu
            
        results = service.files().list(**kwargs).execute()
        items = results.get('files', [])
        if not items:
            return "Drive'da dosya bulunamadı."

        ozet = "📂 Drive Dosyalarınız:\n"
        for i in items:
            name = i['name']
            modified = i.get('modifiedTime', '')
            try:
                dt = datetime.datetime.fromisoformat(modified.replace('Z', '+00:00'))
                tarih_str = dt.strftime('%d/%m %H:%M')
            except (ValueError, AttributeError):
                tarih_str = ""
            suffix = f" ({tarih_str})" if tarih_str else ""
            ozet += f"  • {name}{suffix}\n"
        return ozet
    except HttpError as e:
        logger.error("Drive API hatası [%s]: %s", e.resp.status, e)
        return f"Drive hatası ({e.resp.status}): {e._get_reason()}"
    except Exception as e:
        logger.error("Drive hatası: %s", e)
        return f"Drive hatası: {e}"


# Windows'ta dosya adı olarak kullanılamayan rezerve aygıt adları
_WINDOWS_RESERVED_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)

# Tıklanınca çalıştırılabilecek tehlikeli uzantılar — indirme engellenir.
# (Drive'a paylaşılan kötü niyetli bir dosyanın indirilip çalıştırılmasını önler.)
_BLOCKED_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".scr", ".ps1", ".psm1", ".vbs", ".vbe",
    ".js", ".jse", ".wsf", ".wsh", ".msi", ".msp", ".lnk", ".pif", ".hta",
    ".jar", ".reg", ".dll", ".app", ".sh",
}


def _safe_filename(name: str) -> str:
    """Dosya adını güvenli hale getirir (path traversal + Windows özel adları)."""
    safe = os.path.basename(name)
    # Tehlikeli karakterleri temizle
    safe = re.sub(r'[<>:"/\\|?*]', '_', safe)
    # Windows sondaki nokta/boşlukları sessizce düşürür — belirsizliği önle
    safe = safe.rstrip(". ")
    # Rezerve aygıt adlarını etkisizleştir (CON, NUL, COM1...)
    if safe.split(".")[0].upper() in _WINDOWS_RESERVED_NAMES:
        safe = "_" + safe
    return safe if safe else "indirilen_dosya"


def drive_dosya_indir(dosya_adi: str) -> str:
    """
    Belirtilen ada sahip veya adı belirtilen metni içeren dosyayı Drive'dan bulup güvenli bir klasöre indirir.

    Args:
        dosya_adi: İndirilecek dosyanın Drive'daki adı veya adının bir kısmı.

    Returns:
        str: Başarı veya hata mesajı.
    """
    try:
        service = _get_service('drive', 'v3')
        safe_query = _sanitize_query(dosya_adi)
        results = service.files().list(
            q=f"name contains '{safe_query}'",
            spaces='drive',
            fields='files(id, name, size)'
        ).execute()
        items = results.get('files', [])
        if not items:
            return f"❌ '{dosya_adi}' içeren bir dosya Drive'da bulunamadı. Lütfen önce drive_listele(sorgu=\"name contains '{safe_query}'\") aracını kullanarak dosyanın tam adını kontrol et."

        file_meta = items[0]
        file_id = file_meta['id']
        file_name = _safe_filename(file_meta['name'])
        file_size = int(file_meta.get('size', 0))

        # Çalıştırılabilir dosya engeli (indir + tıkla = kod çalıştırma riskine karşı)
        uzanti = os.path.splitext(file_name)[1].lower()
        if uzanti in _BLOCKED_EXTENSIONS:
            return (
                f"❌ Güvenlik: '{file_name}' çalıştırılabilir bir dosya türü ({uzanti}) "
                "olduğu için indirilmedi. Yalnızca belge/medya dosyaları indirilebilir."
            )

        # Boyut kontrolü
        max_bytes = MAX_DOWNLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            size_mb = file_size / (1024 * 1024)
            return (
                f"❌ '{file_name}' dosyası çok büyük ({size_mb:.1f} MB). "
                f"Maksimum indirme limiti: {MAX_DOWNLOAD_SIZE_MB} MB."
            )

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        save_path = os.path.join(DOWNLOAD_DIR, file_name)

        # Buffered download
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                logger.info("İndirme ilerleme: %d%%", int(status.progress() * 100))

        # Atomic write
        with open(save_path, 'wb') as f:
            f.write(buffer.getvalue())

        size_info = f" ({file_size / 1024:.1f} KB)" if file_size else ""
        return f"✅ '{file_name}'{size_info} başarıyla '{DOWNLOAD_DIR}' klasörüne indirildi."
    except HttpError as e:
        logger.error("Drive indirme API hatası [%s]: %s", e.resp.status, e)
        return f"Drive indirme hatası ({e.resp.status}): {e._get_reason()}"
    except Exception as e:
        logger.error("Drive indirme hatası: %s", e)
        return f"Drive indirme hatası: {e}"


def yerel_dosya_oku(dosya_adi: str) -> str:
    """
    Yerel 'downloads' klasöründeki dosyayı okur (PDF, DOCX, TXT vb.) ve içeriğini döndürür.
    
    Args:
        dosya_adi: Okunacak dosyanın adı.
        
    Returns:
        str: Dosya içeriği (veya özetlenmiş içeriği) ya da hata mesajı.
    """
    dosya_yolu = os.path.join(DOWNLOAD_DIR, dosya_adi)

    # Path traversal koruması: hedef, downloads klasörünün İÇİNDE olmalı.
    # (Ayraçlı karşılaştırma — 'downloads_evil' gibi kardeş klasör bypass'ını önler.)
    base_dir = os.path.abspath(DOWNLOAD_DIR)
    hedef = os.path.abspath(dosya_yolu)
    if not hedef.startswith(base_dir + os.sep):
        return "❌ Hata: Dosya yoluna erişim engellendi."
        
    if not os.path.exists(dosya_yolu):
        dosya_listesi = ", ".join(os.listdir(DOWNLOAD_DIR)) if os.path.exists(DOWNLOAD_DIR) else "Yok"
        return f"❌ '{dosya_adi}' bulunamadı. Lütfen tam dosya adını verin. İndirilen dosyalar: {dosya_listesi}"
        
    uzanti = os.path.splitext(dosya_adi)[1].lower()
    icerik = ""
    
    try:
        if uzanti == '.pdf':
            if not PdfReader:
                return "❌ Hata: 'pypdf' kütüphanesi kurulu değil."
            reader = PdfReader(dosya_yolu)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    icerik += text + "\n"
                    
        elif uzanti in ['.docx', '.doc']:
            if not docx:
                return "❌ Hata: 'python-docx' kütüphanesi kurulu değil."
            doc = docx.Document(dosya_yolu)
            icerik = "\n".join([p.text for p in doc.paragraphs])
            
        else:
            # Metin tabanlı dosya okuma (txt, md, csv vb)
            try:
                with open(dosya_yolu, "r", encoding="utf-8") as f:
                    icerik = f.read()
            except UnicodeDecodeError:
                return f"❌ '{dosya_adi}' metin tabanlı bir dosya değil veya desteklenmeyen format. (Sadece PDF, DOCX, TXT okuyabilirim)"
                
        icerik = icerik.strip()
        if not icerik:
            return f"⚠️ '{dosya_adi}' dosyası okundu fakat içi boş veya metin çıkarılamadı."
            
        # İçeriği sınırla — LLM token limitine takılmamak için.
        max_limit = FILE_READ_CHAR_LIMIT
        if len(icerik) > max_limit:
            icerik = icerik[:max_limit] + f"\n\n... (Dosya çok uzundu, ilk {max_limit} karakter okundu)"
            
        return f"📄 **{dosya_adi} İçeriği:**\n{icerik}"
        
    except Exception as e:
        logger.error(f"Dosya okuma hatası ({dosya_adi}): {e}")
        return f"❌ '{dosya_adi}' okunurken bir hata oluştu: {e}"


# ─── Docs ───

def docs_belge_olustur(baslik: str, icerik: str) -> str:
    """
    Google Docs üzerinde yeni bir belge oluşturur ve içeriğini yazar.

    Args:
        baslik: Belge başlığı.
        icerik: Belge içeriği.

    Returns:
        str: Başarı veya hata mesajı.
    """
    try:
        service = _get_service('docs', 'v1')
        doc = service.documents().create(body={'title': baslik}).execute()
        doc_id = doc.get('documentId')
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"

        if icerik:
            requests = [
                {
                    'insertText': {
                        'location': {'index': 1},
                        'text': icerik
                    }
                }
            ]
            service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()

        return f"✅ '{baslik}' adlı doküman oluşturuldu.\n🔗 {doc_url}"
    except HttpError as e:
        logger.error("Docs API hatası [%s]: %s", e.resp.status, e)
        return f"Docs oluşturma hatası ({e.resp.status}): {e._get_reason()}"
    except Exception as e:
        logger.error("Docs oluşturma hatası: %s", e)
        return f"Docs oluşturma hatası: {e}"
