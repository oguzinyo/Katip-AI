"""
Widget-based chat view for Katip.
Gerçek yuvarlak köşeli mesaj kartları, mesaj kopyalama, karşılama ekranı
ve temiz token-streaming — QTextBrowser'ın zengin-metin kısıtları olmadan.
"""
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QToolButton, QVBoxLayout, QWidget
)
from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal

from core.config import COLORS, APP_NAME, APP_TAGLINE
from ui import icons

# Balonun sohbet alanına oranla maksimum genişliği
_BUBBLE_MAX_RATIO = 0.78
_STREAM_CURSOR = " ▍"


class MessageBubble(QFrame):
    """Tek bir sohbet mesajı kartı: başlık (isim + saat + kopyala) ve gövde."""

    def __init__(self, sender: str, is_user: bool, ts: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("userBubble" if is_user else "asstBubble")
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self._raw: str = ""

        accent = COLORS["accent_emerald"] if is_user else COLORS["accent_indigo"]

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(5)

        # ─── Başlık satırı ───
        header = QHBoxLayout()
        header.setSpacing(8)

        name = QLabel(sender)
        name.setStyleSheet(
            f"color: {accent}; font-size: 12px; font-weight: 700;"
            " letter-spacing: 0.5px; background: transparent;"
        )
        header.addWidget(name)

        if ts:
            time_label = QLabel(ts)
            time_label.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;"
            )
            header.addWidget(time_label)

        header.addStretch(1)

        self.copy_btn = QToolButton()
        self.copy_btn.setObjectName("copyBtn")
        self.copy_btn.setIcon(icons.svg_icon("copy", COLORS["text_muted"], 14))
        self.copy_btn.setIconSize(QSize(14, 14))
        self.copy_btn.setFixedSize(24, 24)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setToolTip("Kopyala")
        self.copy_btn.clicked.connect(self._copy_to_clipboard)
        header.addWidget(self.copy_btn)

        root.addLayout(header)

        # ─── Gövde ───
        self.body = QLabel()
        self.body.setObjectName("bubbleBody")
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.body.setOpenExternalLinks(True)
        root.addWidget(self.body)

    # ─── İçerik API'si ───

    def set_plain(self, text: str) -> None:
        """Düz metin içerik (kullanıcı mesajları — HTML olarak yorumlanmaz)."""
        self._raw = text
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setText(text)

    def set_rich(self, html: str, raw: str) -> None:
        """Zengin (markdown'dan HTML) içerik. 'raw' kopyalamada kullanılır."""
        self._raw = raw
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setText(html)

    def stream_append(self, token: str) -> None:
        """Streaming sırasında token ekler (düz metin + imleç)."""
        self._raw += token
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setText(self._raw + _STREAM_CURSOR)

    def finish_stream(self) -> None:
        """Streaming imlecini kaldırır (nihai render'dan önce güvenli hal)."""
        self.body.setTextFormat(Qt.TextFormat.PlainText)
        self.body.setText(self._raw)

    @property
    def raw_text(self) -> str:
        return self._raw

    # ─── Kopyalama ───

    def _copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self._raw)
        self.copy_btn.setIcon(icons.svg_icon("check", COLORS["accent_emerald"], 14))
        QTimer.singleShot(
            1200,
            lambda: self.copy_btn.setIcon(icons.svg_icon("copy", COLORS["text_muted"], 14)),
        )


class ChatView(QFrame):
    """
    Sohbet alanı: boşken karşılama ekranı (logo + örnek komut çipleri),
    mesaj geldiğinde kaydırılabilir balon listesi.
    """

    suggestion_clicked = pyqtSignal(str)

    def __init__(self, suggestions: list[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("chatArea")
        self._bubbles: list[MessageBubble] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        outer.addWidget(self._stack)

        self._stack.addWidget(self._build_welcome_page(suggestions))  # index 0
        self._stack.addWidget(self._build_chat_page())                # index 1
        self._stack.setCurrentIndex(0)

    # ─── Sayfalar ───

    def _build_welcome_page(self, suggestions: list[str]) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(3)

        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(52))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo)
        layout.addSpacing(14)

        title = QLabel(APP_NAME)
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        tagline = QLabel(APP_TAGLINE)
        tagline.setObjectName("welcomeTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(tagline)
        layout.addSpacing(26)

        # Öneri çipleri — ortalanmış sabit genişlikli sütun
        chips_holder = QWidget()
        chips_col = QVBoxLayout(chips_holder)
        chips_col.setContentsMargins(0, 0, 0, 0)
        chips_col.setSpacing(8)
        for text in suggestions:
            chip = QPushButton(text)
            chip.setObjectName("suggestionChip")
            chip.setMinimumHeight(42)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, t=text: self.suggestion_clicked.emit(t))
            chips_col.addWidget(chip)
        chips_holder.setFixedWidth(400)

        center_row = QHBoxLayout()
        center_row.addStretch(1)
        center_row.addWidget(chips_holder)
        center_row.addStretch(1)
        layout.addLayout(center_row)

        layout.addStretch(4)
        return page

    def _build_chat_page(self) -> QWidget:
        self._scroll = QScrollArea()
        self._scroll.setObjectName("chatScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("chatContainer")
        self._messages_layout = QVBoxLayout(container)
        self._messages_layout.setContentsMargins(16, 16, 16, 16)
        self._messages_layout.setSpacing(12)
        self._messages_layout.addStretch(1)

        self._scroll.setWidget(container)

        # Yeni içerik geldikçe otomatik en alta kaydır
        bar = self._scroll.verticalScrollBar()
        bar.rangeChanged.connect(lambda _min, _max: bar.setValue(_max))

        return self._scroll

    # ─── Genel API ───

    def add_bubble(self, sender: str, is_user: bool, ts: str = "") -> MessageBubble:
        """Yeni mesaj balonu ekler ve döndürür."""
        self._stack.setCurrentIndex(1)

        bubble = MessageBubble(sender, is_user, ts)
        self._bubbles.append(bubble)
        bubble.setMaximumWidth(self._bubble_max_width())

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        if is_user:
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)

        # Alt stretch'in üstüne yerleştir
        self._messages_layout.insertWidget(self._messages_layout.count() - 1, row)
        return bubble

    def clear(self) -> None:
        """Tüm mesajları kaldırıp karşılama ekranına döner."""
        while self._messages_layout.count() > 1:
            item = self._messages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._bubbles.clear()
        self._stack.setCurrentIndex(0)

    def has_messages(self) -> bool:
        return bool(self._bubbles)

    # ─── Genişlik Yönetimi ───

    def _bubble_max_width(self) -> int:
        viewport = self._scroll.viewport().width() if self._scroll.viewport() else self.width()
        base = viewport if viewport > 0 else 640
        return max(280, int(base * _BUBBLE_MAX_RATIO))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        width = self._bubble_max_width()
        for bubble in self._bubbles:
            bubble.setMaximumWidth(width)
