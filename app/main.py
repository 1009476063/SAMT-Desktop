"""Application entry point."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    app_root = Path(__file__).resolve().parent
    sys.path.insert(0, str(app_root))
    # The exact-reference CPU backend uses all physical cores for 3D convs.
    # Setting this before torch import avoids a slow one-thread first run.
    import os
    cpu_count = os.cpu_count() or 4
    os.environ.setdefault("OMP_NUM_THREADS", str(cpu_count))
    os.environ.setdefault("MKL_NUM_THREADS", str(cpu_count))
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow
    from ui.theme import application_font, palette, stylesheet

    app = QApplication(sys.argv)
    app.setApplicationName("SAMT Desktop")
    app.setApplicationVersion("1.1.1")
    app.setFont(application_font())
    app.setPalette(palette())
    app.setStyleSheet(stylesheet())
    app.setAttribute(Qt.AA_DontShowIconsInMenus, False)
    window = MainWindow()
    window.show()
    window.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
