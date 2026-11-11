"""Qt design tokens for the SAMT research workbench."""
from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QFont, QPalette


COLORS = {
    "window": "#f4f6f7",
    "surface": "#ffffff",
    "surface_alt": "#eef2f3",
    "ink": "#17232b",
    "muted": "#586871",
    "border": "#cbd5d9",
    "accent": "#0c6d72",
    "accent_hover": "#095a5f",
    "accent_soft": "#dcecec",
    "positive": "#9a3e32",
    "negative": "#2d6b58",
    "warning": "#8b5b18",
    "disabled": "#e4e9eb",
}


def application_font() -> QFont:
    families = ["PingFang SC", "Microsoft YaHei UI", "Segoe UI", "Helvetica Neue"]
    if sys.platform != "darwin":
        families = ["Microsoft YaHei UI", "Segoe UI", "PingFang SC", "Helvetica Neue"]
    font = QFont()
    font.setFamilies(families)
    font.setPointSize(10)
    return font


def palette() -> QPalette:
    p = QPalette()
    p.setColor(QPalette.Window, QColor(COLORS["window"]))
    p.setColor(QPalette.WindowText, QColor(COLORS["ink"]))
    p.setColor(QPalette.Base, QColor(COLORS["surface"]))
    p.setColor(QPalette.AlternateBase, QColor(COLORS["surface_alt"]))
    p.setColor(QPalette.Text, QColor(COLORS["ink"]))
    p.setColor(QPalette.Button, QColor(COLORS["surface"]))
    p.setColor(QPalette.ButtonText, QColor(COLORS["ink"]))
    p.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor(COLORS["accent"]))
    return p


def stylesheet() -> str:
    """One light theme, one radius scale, and native-platform control sizing."""
    return f"""
    QMainWindow, QDialog {{
        background: {COLORS['window']};
        color: {COLORS['ink']};
    }}
    QWidget {{
        font-family: "PingFang SC", "Microsoft YaHei UI", "Segoe UI", sans-serif;
        font-size: 10pt;
    }}
    QLabel[role="title"] {{
        font-size: 20pt;
        font-weight: 600;
        letter-spacing: 0px;
    }}
    QLabel[role="section"] {{
        font-size: 12pt;
        font-weight: 600;
    }}
    QLabel[role="caption"] {{
        color: {COLORS['muted']};
        font-size: 9pt;
    }}
    QLabel[role="metric"] {{
        font-size: 24pt;
        font-weight: 600;
    }}
    QLabel[role="probability"] {{
        font-size: 26pt;
        font-weight: 600;
        color: {COLORS['accent']};
    }}
    QFrame[role="panel"] {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
    }}
    QFrame[role="rail"] {{
        background: {COLORS['surface']};
        border-right: 1px solid {COLORS['border']};
    }}
    QFrame[role="header"] {{
        background: {COLORS['surface']};
        border-bottom: 1px solid {COLORS['border']};
    }}
    QFrame[role="divider"] {{
        color: {COLORS['border']};
    }}
    QPushButton {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 5px;
        min-height: 30px;
        padding: 5px 12px;
        color: {COLORS['ink']};
    }}
    QPushButton:hover {{ background: {COLORS['surface_alt']}; }}
    QPushButton:pressed {{ background: {COLORS['accent_soft']}; }}
    QPushButton:focus-visible {{ border: 2px solid {COLORS['accent']}; }}
    QPushButton:disabled {{
        color: {COLORS['muted']};
        background: {COLORS['disabled']};
    }}
    QPushButton[role="primary"] {{
        background: {COLORS['accent']};
        color: #ffffff;
        border-color: {COLORS['accent']};
        font-weight: 600;
    }}
    QPushButton[role="primary"]:hover {{ background: {COLORS['accent_hover']}; }}
    QPushButton[role="primary"]:disabled {{
        background: {COLORS['disabled']};
        color: {COLORS['muted']};
        border-color: {COLORS['border']};
    }}
    QPushButton[role="nav"] {{
        text-align: left;
        border: 0px;
        border-radius: 5px;
        padding: 9px 12px;
        min-height: 38px;
        font-size: 10pt;
    }}
    QPushButton[role="nav"]:checked {{
        background: {COLORS['accent_soft']};
        color: {COLORS['accent_hover']};
        font-weight: 600;
        border-left: 3px solid {COLORS['accent']};
        padding-left: 9px;
    }}
    QLineEdit, QComboBox, QTextEdit, QSpinBox, QDoubleSpinBox {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 5px;
        min-height: 28px;
        padding: 4px 8px;
        selection-background-color: {COLORS['accent_soft']};
        selection-color: {COLORS['ink']};
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
        border: 2px solid {COLORS['accent']};
        padding: 3px 7px;
    }}
    QComboBox::drop-down {{ width: 26px; border: 0px; }}
    QCheckBox {{ spacing: 8px; }}
    QGroupBox {{
        border: 0px;
        font-weight: 600;
        margin-top: 18px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 0px; padding: 0px 0px 6px 0px; }}
    QProgressBar {{
        border: 1px solid {COLORS['border']};
        border-radius: 5px;
        background: {COLORS['surface']};
        text-align: center;
        min-height: 16px;
        max-height: 16px;
    }}
    QProgressBar::chunk {{
        background: {COLORS['accent']};
        border-radius: 4px;
        margin: 1px;
    }}
    QTableWidget, QTableView {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        gridline-color: {COLORS['border']};
        selection-background-color: {COLORS['accent_soft']};
        selection-color: {COLORS['ink']};
    }}
    QHeaderView::section {{
        background: {COLORS['surface_alt']};
        border: 0px;
        border-bottom: 1px solid {COLORS['border']};
        padding: 7px;
        font-weight: 600;
    }}
    QTabWidget::pane {{ border: 0px; }}
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: {COLORS['window']};
        border: 0px;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background: {COLORS['border']};
        border-radius: 4px;
    }}
    QStatusBar {{
        background: {COLORS['surface']};
        border-top: 1px solid {COLORS['border']};
        color: {COLORS['muted']};
    }}
    """
