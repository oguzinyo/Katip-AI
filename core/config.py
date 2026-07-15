"""
Configuration constants and settings for Katip.
"""
import os
import logging

# ─── Uygulama Kimliği ───
APP_NAME: str = "Katip"
APP_TAGLINE: str = "Mail  •  Takvim  •  Drive  •  Docs"

# ─── Ollama Model ───
MODEL_NAME: str = os.getenv("OLLAMA_MODEL", "gemma3:12b")
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))   # Saniye — Ollama istek zaman aşımı

# ─── Google OAuth Scopes ───
# Not: Gmail YALNIZCA okuma izni (readonly). 'gmail.send'/'gmail.compose' bilinçli
# olarak verilmez; böylece uygulama teknik olarak e-posta gönderemez.
SCOPES: list[str] = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive'
]

# ─── Dosya Yolları ───
BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE: str = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE: str = os.path.join(BASE_DIR, "token.json")

# ─── Uygulama Ayarları ───
SESSIONS_FILE: str = os.path.join(BASE_DIR, "chat_sessions.json")
CHAT_HISTORY_FILE: str = os.path.join(BASE_DIR, "chat_history.json")  # Eski format (migrasyon için)
MAX_HISTORY_LENGTH: int = 20          # System prompt hariç tutulacak max mesaj sayısı
LISTEN_DURATION_SECONDS: int = 5      # Mikrofon dinleme süresi
LISTEN_SAMPLE_RATE: int = 44100       # Ses örnekleme hızı
DOWNLOAD_DIR: str = os.path.join(BASE_DIR, "downloads")
MAX_DOWNLOAD_SIZE_MB: int = 100       # Drive indirme boyut limiti (MB)

# ─── Asistan Davranışı ───
MAX_TOOL_ITERATIONS: int = 5          # Tek bir komutta zincirlenebilecek max araç çağrısı
MAX_RETRIES: int = 3                  # Ollama bağlantı hatasında tekrar deneme sayısı
FILE_READ_CHAR_LIMIT: int = 4000      # yerel_dosya_oku için max karakter (token limiti)
GMAIL_BODY_CHAR_LIMIT: int = 2000     # E-posta gövdesi için max karakter

# ─── Karşılama Ekranı Önerileri ───
WELCOME_SUGGESTIONS: list[str] = [
    "Son 3 mailimi özetle",
    "Bu haftaki takvim etkinliklerim neler?",
    "Drive'daki son dosyaları listele",
    "Yarın 14:00'e 'Toplantı' etkinliği ekle",
]

# ─── Renk Paleti ───
# Rafine koyu "slate + indigo" tema. Nötr zeminler + tek güçlü vurgu (indigo).
COLORS: dict[str, str] = {
    # Arka plan katmanları (koyudan yükseltilmişe)
    "bg_primary":      "#0a0d14",   # pencere zemini
    "bg_secondary":    "#0e121b",   # panel yüzeyleri (sidebar, header, chat)
    "bg_card":         "#161b27",   # kart / balon yüzeyi
    "bg_elevated":     "#12161f",   # tooltip, yükseltilmiş öğeler
    "bg_input":        "rgba(255, 255, 255, 0.04)",

    # Kenarlıklar (nötr beyaz-alfa — daha profesyonel)
    "border":          "rgba(255, 255, 255, 0.09)",
    "border_hover":    "rgba(129, 140, 248, 0.45)",
    "border_subtle":   "rgba(255, 255, 255, 0.06)",

    # Vurgu renkleri
    "accent_indigo":   "#818cf8",
    "accent_purple":   "#a78bfa",
    "accent_emerald":  "#34d399",
    "accent_rose":     "#fb7185",
    "accent_amber":    "#fbbf24",
    "accent_sky":      "#38bdf8",

    # Metin hiyerarşisi
    "text_primary":    "#f1f5f9",
    "text_secondary":  "#9aa6b8",
    "text_muted":      "#5b6678",

    # Sohbet balonları
    "user_bubble":     "#1b2230",
    "user_border":     "rgba(52, 211, 153, 0.45)",
    "asst_bubble":     "#141a26",
    "asst_border":     "rgba(129, 140, 248, 0.45)",
}

# ─── Logging Yapılandırması ───
LOG_FORMAT: str = "[%(levelname)s] %(name)s — %(message)s"
LOG_LEVEL: int = logging.INFO
