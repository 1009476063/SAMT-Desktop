"""Visible-widget language purity checks on the live main window."""
import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from i18n import I18n  # noqa: E402
from ui.main_window import MainWindow, ResearchUseGate  # noqa: E402


def _visible_text(qt_root):
    from PySide6.QtWidgets import QCheckBox, QLabel, QPushButton, QTableWidget

    ignored = {"S", "N", "--", "CPU", "CUDA", "MPS", "0", "10 / 10"}
    texts = []
    for widget in (qt_root.findChildren(QLabel)
                   + qt_root.findChildren(QPushButton)
                   + qt_root.findChildren(QCheckBox)):
        text = widget.text().strip()
        if text and text not in ignored:
            texts.append(text)
    for table in qt_root.findChildren(QTableWidget):
        for column in range(table.columnCount()):
            item = table.horizontalHeaderItem(column)
            if item:
                texts.append(item.text())
    return texts


def test_visible_widgets_are_language_pure():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    MainWindow._prepare_engine = lambda self: None
    window = MainWindow()
    window.i18n.set_language("en-US")
    window._apply_language("en-US")
    assert not [text for text in _visible_text(window)
                if re.search(r"[\u4e00-\u9fff]", text)]

    window._apply_language("zh-CN")
    domain_terms = (
        "SAMT", "DCE", "MLO", "N4", "decay1", "CPU", "CUDA", "MPS",
        "CP.xlsx", "MRMG", "Positive", "Negative", "NSLN", "ER", "PR",
        "HER2", "Ki67", "ALN", "SLN", "ID", "CSV", "AUC", "ACC",
        "softmax", "NIfTI", "CaseID",
    )
    latin_phrases = [
        text for text in _visible_text(window)
        if re.search(r"[A-Za-z]{4,}", text)
        and not any(term in text for term in domain_terms)
    ]
    assert not latin_phrases
    window.close()


def test_consent_gate_switches_language_in_place():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    settings = type("S", (), {
        "data": {"disclaimer_accepted": False,
                 "accepted_disclaimer_version": ""},
        "save": lambda self: None,
    })()
    gate = ResearchUseGate(I18n("en-US"), settings)
    assert not any(re.search(r"[\u4e00-\u9fff]", text)
                   for text in _visible_text(gate))
    gate._toggle_language()
    assert re.search(r"[\u4e00-\u9fff]", gate.body.toPlainText())
    gate.close()
