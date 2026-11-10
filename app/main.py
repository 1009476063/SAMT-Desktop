"""Application entry point."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    app_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(app_root))
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("SAMT Desktop")
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
