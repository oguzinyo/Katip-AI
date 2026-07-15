"""
Stylesheet bindings and GUI themes for the Assistant App.
Refined dark "slate + indigo" theme — layered panels, neutral borders,
a single confident accent, and system typography.
"""
from core.config import COLORS

GLOBAL_STYLE = f"""
/* ─── Global ─── */
* {{
    font-family: "Segoe UI", "Inter", -apple-system, system-ui, "Helvetica Neue", sans-serif;
    font-size: 14px;
}}

QMainWindow, QWidget#centralWidget {{
    background: {COLORS["bg_primary"]};
}}

QToolTip {{
    background: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 8px;
    padding: 6px 10px;
}}

QMenu {{
    background: {COLORS["bg_elevated"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 10px;
    padding: 6px;
}}

QMenu::item {{
    padding: 7px 22px 7px 14px;
    border-radius: 7px;
    font-size: 13px;
}}

QMenu::item:selected {{
    background: rgba(129, 140, 248, 0.15);
}}

/* ─── Sidebar Panel ─── */
QFrame#sidebarFrame {{
    background: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 18px;
}}

/* ─── Header ─── */
QFrame#headerFrame {{
    background: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 18px;
    padding: 14px 22px;
}}

QLabel#headerTitle {{
    color: {COLORS["text_primary"]};
    font-size: 21px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

QLabel#headerSubtitle {{
    color: {COLORS["text_secondary"]};
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 2px;
}}

/* ─── Chat Area ─── */
QFrame#chatArea {{
    background: {COLORS["bg_secondary"]};
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 18px;
}}

QScrollArea#chatScroll {{
    background: transparent;
    border: none;
}}

QScrollArea#chatScroll > QWidget > QWidget#chatContainer {{
    background: transparent;
}}

/* ─── Mesaj Balonları ─── */
QFrame#userBubble {{
    background: {COLORS["user_bubble"]};
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 14px;
    border-bottom-right-radius: 4px;
}}

QFrame#asstBubble {{
    background: {COLORS["asst_bubble"]};
    border: 1px solid {COLORS["border_subtle"]};
    border-radius: 14px;
    border-bottom-left-radius: 4px;
}}

QLabel#bubbleBody {{
    color: {COLORS["text_primary"]};
    font-size: 14px;
    background: transparent;
}}

QToolButton#copyBtn {{
    background: transparent;
    border: none;
    border-radius: 6px;
}}

QToolButton#copyBtn:hover {{
    background: rgba(255, 255, 255, 0.08);
}}

/* ─── Karşılama Ekranı ─── */
QLabel#welcomeTitle {{
    color: {COLORS["text_primary"]};
    font-size: 26px;
    font-weight: 700;
    letter-spacing: 0.5px;
    background: transparent;
}}

QLabel#welcomeTagline {{
    color: {COLORS["text_muted"]};
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 2px;
    background: transparent;
}}

QPushButton#suggestionChip {{
    background: {COLORS["bg_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 12px;
    padding: 10px 16px;
    color: {COLORS["text_secondary"]};
    font-size: 13px;
    text-align: left;
}}

QPushButton#suggestionChip:hover {{
    background: rgba(129, 140, 248, 0.1);
    border: 1px solid {COLORS["accent_indigo"]};
    color: {COLORS["text_primary"]};
}}

QPushButton#suggestionChip:pressed {{
    background: rgba(129, 140, 248, 0.18);
}}

/* ─── Text Input ─── */
QLineEdit#textInput {{
    background: {COLORS["bg_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
    padding: 0 18px;
    color: {COLORS["text_primary"]};
    selection-background-color: rgba(129, 140, 248, 0.35);
}}

QLineEdit#textInput:focus {{
    border: 1px solid {COLORS["accent_indigo"]};
    background: rgba(129, 140, 248, 0.06);
}}

QLineEdit#textInput:disabled {{
    background: rgba(255, 255, 255, 0.02);
    color: {COLORS["text_muted"]};
}}

/* ─── Send Button (primary, filled) ─── */
QPushButton#sendBtn {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #8e96fa,
        stop:1 {COLORS["accent_indigo"]}
    );
    border: none;
    border-radius: 14px;
    color: #0a0d14;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

QPushButton#sendBtn:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #9ba2fb,
        stop:1 #8e96fa
    );
}}

QPushButton#sendBtn:pressed {{
    background: {COLORS["accent_indigo"]};
}}

QPushButton#sendBtn:disabled {{
    background: rgba(129, 140, 248, 0.18);
    color: rgba(241, 245, 249, 0.4);
}}

/* ─── Mic Button (secondary, outline) ─── */
QPushButton#micBtn {{
    background: {COLORS["bg_input"]};
    border: 1px solid {COLORS["border"]};
    border-radius: 14px;
    color: {COLORS["text_primary"]};
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

QPushButton#micBtn:hover {{
    background: rgba(129, 140, 248, 0.1);
    border: 1px solid {COLORS["accent_indigo"]};
}}

QPushButton#micBtn:pressed {{
    background: rgba(129, 140, 248, 0.18);
}}

QPushButton#micBtn:disabled {{
    background: rgba(255, 255, 255, 0.02);
    color: {COLORS["text_muted"]};
    border-color: {COLORS["border_subtle"]};
}}

/* ─── Cancel Button ─── */
QPushButton#cancelBtn {{
    background: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 {COLORS["accent_rose"]},
        stop:1 #f43f5e
    );
    color: white;
    border: none;
    border-radius: 14px;
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.3px;
}}

QPushButton#cancelBtn:hover {{
    background: {COLORS["accent_rose"]};
}}

QPushButton#cancelBtn:pressed {{
    background: #e11d48;
}}

/* ─── New Chat Button (sidebar) ─── */
QPushButton#newChatBtn {{
    background: rgba(129, 140, 248, 0.12);
    border: 1px solid rgba(129, 140, 248, 0.25);
    border-radius: 12px;
    color: {COLORS["text_primary"]};
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.3px;
}}

QPushButton#newChatBtn:hover {{
    background: rgba(129, 140, 248, 0.2);
    border: 1px solid {COLORS["accent_indigo"]};
}}

QPushButton#newChatBtn:pressed {{
    background: rgba(129, 140, 248, 0.28);
}}

/* ─── Sidebar History List ─── */
QListWidget#historyList {{
    background: transparent;
    border: none;
    padding: 2px;
    color: {COLORS["text_secondary"]};
    font-size: 13px;
    outline: none;
}}

QListWidget#historyList::item {{
    border-radius: 10px;
    padding: 10px 12px;
    margin: 2px 0px;
    color: {COLORS["text_secondary"]};
}}

QListWidget#historyList::item:hover {{
    background: rgba(255, 255, 255, 0.04);
    color: {COLORS["text_primary"]};
}}

QListWidget#historyList::item:selected {{
    background: rgba(129, 140, 248, 0.15);
    color: {COLORS["text_primary"]};
    font-weight: 500;
}}

/* ─── Status Bar ─── */
QLabel#statusLabel {{
    color: {COLORS["text_secondary"]};
    font-size: 12px;
    font-weight: 500;
    padding: 2px 6px;
}}

/* ─── Scrollbars ─── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 6px 3px;
}}

QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 0.12);
    border-radius: 5px;
    min-height: 36px;
}}

QScrollBar::handle:vertical:hover {{
    background: rgba(129, 140, 248, 0.5);
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 3px 6px;
}}

QScrollBar::handle:horizontal {{
    background: rgba(255, 255, 255, 0.12);
    border-radius: 5px;
    min-width: 36px;
}}

QScrollBar::handle:horizontal:hover {{
    background: rgba(129, 140, 248, 0.5);
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0px;
    height: 0px;
}}

QScrollBar::add-page, QScrollBar::sub-page {{
    background: transparent;
}}
"""
