"""
Google API Authentication handling with automatic token refresh.
"""
import logging
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

from core.config import SCOPES, CREDENTIALS_FILE, TOKEN_FILE

logger = logging.getLogger(__name__)

_cached_creds: Optional[Credentials] = None


def get_google_creds() -> Credentials:
    """
    Google API kimlik bilgilerini döndürür.
    - Geçerli token varsa cache'den döner.
    - Süresi dolmuşsa otomatik yeniler (refresh).
    - Hiç yoksa yeni OAuth akışı başlatır.

    Returns:
        Credentials: Geçerli Google OAuth2 kimlik bilgileri.

    Raises:
        FileNotFoundError: credentials.json bulunamazsa.
        Exception: OAuth akışı başarısız olursa.
    """
    global _cached_creds
    if _cached_creds and _cached_creds.valid:
        return _cached_creds

    creds = _load_existing_token()

    # Token var ama süresi dolmuş → yenile
    if creds and creds.expired and creds.refresh_token:
        creds = _try_refresh(creds)

    # Hâlâ geçerli bir token yoksa yeni OAuth akışı başlat
    if not creds or not creds.valid:
        logger.info("Yeni OAuth akışı başlatılıyor...")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=8080, prompt='consent')
        _save_token(creds)

    _cached_creds = creds
    return creds


def invalidate_cache() -> None:
    """Cached credential'ı sıfırlar (yeniden kimlik doğrulama gerektiğinde)."""
    global _cached_creds
    _cached_creds = None
    logger.info("Credential cache temizlendi.")


def _load_existing_token() -> Optional[Credentials]:
    """Disk üzerindeki token dosyasını yüklemeye çalışır."""
    try:
        import os
        if os.path.exists(TOKEN_FILE):
            return Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    except Exception as e:
        logger.warning("Token dosyası okunamadı: %s", e)
    return None


def _try_refresh(creds: Credentials) -> Optional[Credentials]:
    """Süresi dolmuş token'ı yenilemeye çalışır."""
    try:
        logger.info("Token süresi dolmuş, yenileniyor...")
        creds.refresh(Request())
        _save_token(creds)
        return creds
    except Exception as e:
        logger.warning("Token yenileme başarısız: %s — Yeni akış başlatılıyor.", e)
        return None


def _save_token(creds: Credentials) -> None:
    """Token bilgisini diske yazar."""
    try:
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    except Exception as e:
        logger.error("Token kaydetme hatası: %s", e)
