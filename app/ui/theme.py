"""Qt design tokens for the SAMT research workbench."""
from __future__ import annotations

import sys

from PySide6.QtGui import QColor, QFont, QPalette


COLORS = {
    "window": "#f3f7f6",
    "surface": "#ffffff",
    "surface_alt": "#e9f1ef",
    "ink": "#122a2c",
    "muted": "#5c7072",
    "border": "#c4d6d3",
    "accent": "#006f6a",
    "accent_hover": "#005852",
    "accent_soft": "#d9eeea",
    "accent_wash": "#f0f8f6",
    "positive": "#a84235",
    "negative": "#276b55",
    "rose": "#c05263",
    "blue": "#2b6e8f",
    "gold": "#b27a2a",
    "warning": "#8b5b18",
    "warning_soft": "#fbf2df",
    "disabled": "#e6eceb",
    "tree": "#112c2d",
    "tree_text": "#dceeea",
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
        color: {COLORS['ink']};
    }}
    QLabel[role="caption"] {{
        color: {COLORS['muted']};
        font-size: 9pt;
    }}
    QLabel[role="result_note"] {{
        background: {COLORS['accent_wash']};
        border: 1px solid {COLORS['border']};
        border-left: 3px solid {COLORS['gold']};
        border-radius: 5px;
        padding: 9px 12px;
        color: {COLORS['ink']};
    }}
    QLabel[role="metric"] {{
        font-size: 24pt;
        font-weight: 600;
    }}
    QLabel[role="probability"] {{
        font-size: 22pt;
        font-weight: 600;
        color: {COLORS['accent']};
    }}
    QFrame[role="panel"] {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
    }}
    QFrame[role="subpanel"] {{
        background: {COLORS['accent_wash']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
    }}
    QFrame[role="rail"] {{
        background: {COLORS['tree']};
        border-right: 1px solid {COLORS['border']};
    }}
    QFrame[role="rail"] QLabel {{
        color: {COLORS['tree_text']};
    }}
    QFrame[role="rail"] QPushButton {{
        background: {COLORS['surface']};
        color: {COLORS['ink']};
    }}
    QFrame[role="rail"] QPushButton[role="nav"] {{
        background: transparent;
        color: {COLORS['tree_text']};
    }}
    QFrame[role="rail"] QPushButton[role="nav"]:checked {{
        background: #1d4848;
        color: #ffffff;
    }}
    QFrame[role="header"] {{
        background: {COLORS['tree']};
        border-bottom: 1px solid {COLORS['border']};
        border-bottom: 3px solid {COLORS['gold']};
    }}
    QFrame[role="header"] QLabel {{
        color: {COLORS['tree_text']};
    }}
    QFrame[role="header"] QPushButton {{
        background: transparent;
        color: {COLORS['tree_text']};
        border: 1px solid #416763;
    }}
    QFrame[role="header"] QPushButton:hover {{
        background: rgba(255, 255, 255, 0.12);
        border-color: {COLORS['tree_text']};
    }}
    QPushButton[role="header_tool"] {{
        min-height: 34px;
        padding: 0px;
    }}
    QPushButton[role="header_tool"]::menu-indicator {{ image: none; }}
    QFrame[role="divider"] {{
        color: {COLORS['border']};
    }}
    QFrame[role="tree_panel"] {{
        background: {COLORS['tree']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
    }}
    QTextBrowser[role="tree"] {{
        background: {COLORS['tree']};
        color: {COLORS['tree_text']};
        border: 0px;
        border-radius: 0px;
        font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
        font-size: 9pt;
        padding: 4px 12px 12px;
    }}
    QToolButton {{
        border: 0px;
        border-radius: 4px;
        color: {COLORS['ink']};
        min-width: 28px;
        min-height: 26px;
    }}
    QToolButton:hover {{ background: rgba(255, 255, 255, 0.12); }}
    QPushButton {{
        background: {COLORS['surface']};
        border: 1px solid {COLORS['border']};
        border-radius: 5px;
        min-height: 34px;
        padding: 6px 14px 6px 11px;
        color: {COLORS['ink']};
        font-weight: 500;
    }}
    QPushButton:hover {{
        background: {COLORS['accent_soft']};
        border-color: {COLORS['accent']};
    }}
    QPushButton:pressed {{ background: #c9e6e0; }}
    QPushButton:focus-visible {{ border: 2px solid {COLORS['accent']}; }}
    QPushButton:disabled {{
        color: {COLORS['muted']};
        background: {COLORS['disabled']};
    }}
    QPushButton[role="primary"] {{
        background: {COLORS['accent']};
        color: #ffffff;
        border-color: {COLORS['accent']};
        font-weight: 650;
    }}
    QPushButton[role="primary"]:hover {{ background: {COLORS['accent_hover']}; }}
    QPushButton[role="primary"]:disabled {{
        background: {COLORS['disabled']};
        color: {COLORS['muted']};
        border-color: {COLORS['border']};
    }}
    QPushButton[role="primary"] {{ border-bottom: 2px solid {COLORS['accent_hover']}; }}
    QPushButton[role="nav"] {{
        text-align: left;
        border: 0px;
        border-radius: 6px;
        padding: 10px 14px;
        min-height: 40px;
        font-size: 10pt;
        color: {COLORS['tree_text']};
    }}
    QPushButton[role="nav"]:hover {{ background: rgba(255, 255, 255, 0.10); }}
    QPushButton[role="nav"]:checked {{
        background: #1d4848;
        color: #ffffff;
        font-weight: 600;
        border-left: 3px solid {COLORS['gold']};
        padding-left: 11px;
    }}
    QPushButton[role="subtle"] {{
        background: {COLORS['accent_wash']};
        border-color: {COLORS['accent_soft']};
        color: {COLORS['accent_hover']};
        font-weight: 600;
    }}
    QPushButton[role="subtle"]:hover {{
        background: {COLORS['accent_soft']};
        border-color: {COLORS['accent']};
    }}
    QPushButton[role="small"] {{
        min-height: 28px;
        padding: 4px 8px 4px 7px;
        font-size: 9pt;
        border-radius: 5px;
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
    QTableWidget::item {{
        padding: 4px 6px;
    }}
    QTableWidget {{
        gridline-color: #dae5e2;
    }}
    QTableWidget::item:selected {{
        background: {COLORS['accent_soft']};
        color: {COLORS['ink']};
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
        padding: 9px 8px;
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
