"""
Katip — yerel yapay zekâ kâtibiniz.
Sesli/yazılı komutla Gmail, Takvim, Drive ve Docs'u yöneten PyQt6 masaüstü uygulaması.
AI arka ucu: Ollama (varsayılan model: gemma3:12b).
"""
import sys
import logging
from PyQt6.QtWidgets import QApplication
from dotenv import load_dotenv

from core.config import LOG_FORMAT, LOG_LEVEL
from ui.app import App


def main():
    load_dotenv()
    logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

    qt_app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    main()
