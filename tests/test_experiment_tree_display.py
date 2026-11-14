"""Generic, localized experiment tree display regressions."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _catalogs():
    return {
        code: json.loads(
            (APP / "locales" / f"{code}.json").read_text("utf-8"))
        for code in ("en-US", "zh-CN")
    }


def test_tree_is_generic_and_has_four_required_inputs():
    from core.experiment_contract import experiment_tree_description

    catalogs = _catalogs()
    for code, text in (("en-US", catalogs["en-US"]["directory.tree"]),
                       ("zh-CN", catalogs["zh-CN"]["directory.tree"]),
                       ("fallback", experiment_tree_description())):
        assert "/Users/" not in text, code
        assert "<root>/" not in text, code
        assert "├──" in text and "└──" in text, code
        assert "CP.xlsx" in text and "MRMG/" in text, code
        assert "_DCE.nii[.gz]" in text, code
        assert "_DCE_N4.nii[.gz]" in text, code
        assert "_DCE_GTV.nii[.gz]" in text, code
        assert "_DCE_GTVnd1.nii[.gz]" in text, code
        assert "*_MLO.nii[.gz]" in text, code
        assert "*_MLO_GTV.nii[.gz]" in text, code
        assert "*_MLO_GTVnd1.nii[.gz]" in text, code
        assert "case1" not in text and "case2" not in text, code
        assert "NSLN/" not in text, code


def test_tree_is_visible_and_switches_language_without_restart():
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    MainWindow._prepare_engine = lambda self: None
    window = MainWindow()
    window.i18n.set_language("en-US")
    window._apply_language("en-US")
    english = window.structure_browser.toPlainText()
    assert "StudyRoot/" in english
    assert "<Label>" in english and "<CaseID>" in english
    assert "_DCE_GTVnd1" in english

    window._apply_language("zh-CN")
    chinese = window.structure_browser.toPlainText()
    assert "<研究根目录>/" in chinese
    assert "<磁盘类别>" in chinese and "<病例ID>" in chinese
    assert "_DCE_GTVnd1" in chinese
    assert "StudyRoot/" not in chinese and "<Label>" not in chinese
    assert chinese != english
    window._copy_experiment_tree()
    assert QApplication.clipboard().text() == chinese
    window.close()
