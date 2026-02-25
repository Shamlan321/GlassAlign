from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from config import AppConfig
from ui_main import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("GlassAlign")

    config = AppConfig()
    window = MainWindow(config)
    window.resize(1200, 800)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
