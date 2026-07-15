"""
SVG icon factory for Katip.
Lucide-style stroke icons rendered to crisp QIcons at runtime — no binary
asset files needed. Colors are passed per-use so icons match the theme.
"""
from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from core.config import COLORS

# 24x24 viewBox, stroke tabanlı ikon gövdeleri (Lucide/Feather stili)
_STROKE_ICONS: dict[str, str] = {
    "send": (
        '<path d="M22 2 11 13"/>'
        '<path d="M22 2 15 22 11 13 2 9 22 2z"/>'
    ),
    "mic": (
        '<rect x="9" y="2" width="6" height="12" rx="3"/>'
        '<path d="M5 10v1a7 7 0 0 0 14 0v-1"/>'
        '<path d="M12 18v4"/>'
    ),
    "plus": (
        '<path d="M12 5v14"/>'
        '<path d="M5 12h14"/>'
    ),
    "x": (
        '<path d="M18 6 6 18"/>'
        '<path d="M6 6l12 12"/>'
    ),
    "copy": (
        '<rect x="9" y="9" width="12" height="12" rx="2"/>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>'
    ),
    "check": (
        '<path d="M20 6 9 17l-5-5"/>'
    ),
    "trash": (
        '<path d="M3 6h18"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
        '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
    ),
    "message": (
        '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>'
    ),
}

# Dolgu tabanlı logo: dört köşeli "kıvılcım" (Katip yıldızı)
_LOGO_PATH = "M12 2l2.3 7.7L22 12l-7.7 2.3L12 22l-2.3-7.7L2 12l7.7-2.3L12 2z"


def _render(svg: str, size: int) -> QPixmap:
    """SVG string'ini yüksek çözünürlüklü (2x) QPixmap'e çizer."""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
    painter.end()
    pixmap.setDevicePixelRatio(2.0)
    return pixmap


def svg_pixmap(name: str, color: str, size: int = 20) -> QPixmap:
    """Adlandırılmış stroke ikonunu istenen renk ve boyutta QPixmap döndürür."""
    body = _STROKE_ICONS[name]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
    )
    return _render(svg, size)


def svg_icon(name: str, color: str, size: int = 20) -> QIcon:
    """Adlandırılmış stroke ikonunu QIcon olarak döndürür."""
    icon = QIcon()
    icon.addPixmap(svg_pixmap(name, color, size))
    return icon


def logo_pixmap(size: int = 28, color: str | None = None) -> QPixmap:
    """Katip logosunu (dolgu kıvılcım) QPixmap olarak döndürür."""
    c = color or COLORS["accent_indigo"]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<path d="{_LOGO_PATH}" fill="{c}"/></svg>'
    )
    return _render(svg, size)


def app_icon() -> QIcon:
    """Pencere/görev çubuğu ikonu — birden çok boyutta logo."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(size))
    return icon
