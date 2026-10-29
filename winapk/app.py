"""应用入口。"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import __app_name__
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
