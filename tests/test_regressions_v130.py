"""Red-capable checks for the v1.3.0 startup and workbench fixes."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def test_bundle_specs_keep_pillow_for_torchvision():
    import ast

    for name in ("samt-desktop-macos.spec", "samt-desktop-windows.spec"):
        spec = (ROOT / "packaging" / name).read_text("utf-8")
        excludes_match = re.search(r"excludes=\[(.*?)\]", spec, re.S)
        assert excludes_match
        excludes = ast.literal_eval("[" + excludes_match.group(1) + "]")
        assert "PIL" not in excludes, \
            "torchvision imports Pillow during network construction"
        hidden_match = re.search(r"hiddenimports=\[(.*?)\]", spec, re.S)
        assert hidden_match
        hidden = ast.literal_eval("[" + hidden_match.group(1) + "]")
        assert "PIL" in hidden and "PIL.Image" in hidden
        assert "torchvision" in hidden


def test_default_language_is_english():
    from settings import DEFAULTS
    from i18n import I18n

    assert DEFAULTS["language"] == "en-US"
    assert I18n("").lang == "en-US"


def test_gate_does_not_flash_when_consent_is_current():
    source = (APP / "ui" / "main_window.py").read_text("utf-8")
    assert "def has_current_consent" in source
    assert "QTimer.singleShot(0, self.accept)" not in source
    main_source = (APP / "main.py").read_text("utf-8")
    assert "has_current_consent(settings)" in main_source


def test_live_language_switch_updates_open_widgets():
    source = (APP / "ui" / "main_window.py").read_text("utf-8")
    assert "def _apply_language" in source
    assert "def retranslateUi" in source or "retranslate" in source
    assert "next launch" not in (APP / "locales" / "en-US.json").read_text("utf-8")


def test_experiment_tree_contract_scans_root_without_case_hardcoding():
    from core.engine import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS, discover_cases

    root = Path("/tmp") / "samt-generic-root-check"
    root = root.resolve()
    import shutil
    shutil.rmtree(root, ignore_errors=True)
    for label, case_id in (("Negative", "patient_A"), ("Positive", "patient_B")):
        case = root / "MRMG" / label / case_id
        (case / "MG").mkdir(parents=True, exist_ok=True)
        for filename in (
            f"{case_id}_DCE_N4.nii.gz", f"{case_id}_DCE_decay1.nii.gz",
            f"MG/{case_id}_MG_MLO.nii.gz", f"MG/{case_id}_MLO_decay1.nii.gz",
        ):
            (case / filename).write_bytes(b"test")
    rows = []
    for case_id in ("patient_A", "patient_B"):
        row = {column: "0" for column in CLINICAL_COLUMNS + PATHOLOGY_COLUMNS}
        row["ID"] = case_id
        rows.append(row)
    pd.DataFrame(rows).to_excel(root / "CP.xlsx", sheet_name="Sheet1", index=False)
    cases, problems = discover_cases(root)
    assert problems == []
    assert {c.case_id for c in cases} == {"patient_A", "patient_B"}
    assert "NSLN" not in (APP / "core" / "engine.py").read_text("utf-8")
    assert "case2" not in (APP / "core" / "engine.py").read_text("utf-8")
    shutil.rmtree(root, ignore_errors=True)


def test_clinical_coverage_is_available():
    from core.clinical_table import clinical_coverage

    columns = ["Laterality ", "Age"]
    row = {"Laterality ": "Left", "Age": ""}
    report = clinical_coverage(row, columns)
    assert report.filled == 1
    assert report.total == 2
    assert report.missing == ("Age",)


def test_image_preview_module_is_vendored_and_localized():
    preview = (APP / "ui" / "image_preview.py").read_text("utf-8")
    assert "SimpleITK" in preview or "sitk" in preview
    assert "QImage" in preview
    en = (APP / "locales" / "en-US.json").read_text("utf-8")
    zh = (APP / "locales" / "zh-CN.json").read_text("utf-8")
    for key in ("preview.title", "consent.research_only", "consent.regulatory"):
        assert key in en and key in zh


def test_consent_has_substantive_sectioned_content():
    en = (APP / "locales" / "en-US.json").read_text("utf-8")
    assert "medical device" in en.lower()
    assert "physician-patient relationship" in en.lower()
    assert len(re.findall(r"disclaimer\.section\d", en)) >= 4


def test_runtime_language_switch_changes_visible_navigation():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    MainWindow._prepare_engine = lambda self: None
    window = MainWindow()
    window.i18n.set_language("en-US")
    window._apply_language("en-US")
    nav = window.nav_group.button(0)
    assert nav.text() == "Single case"
    window.language_toggle.click()
    assert nav.text() == "单例预测"
    assert window.batch_scan_btn.text() == "扫描病例"
    window.language_toggle.click()
    assert nav.text() == "Single case"
    assert window.batch_scan_btn.text() == "Scan cases"
    window.close()
