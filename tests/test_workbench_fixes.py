"""Fast, deterministic regression tests for the v1.3.0 workbench fixes."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import importlib.util
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _offscreen_python(snippet: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["SAMT_PROJECT_ROOT"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-c", snippet], cwd=ROOT, env=env,
        text=True, capture_output=True, timeout=30,
    )


def test_ui_shell_import_does_not_load_model_or_dataframe_stack():
    result = _offscreen_python(
        "import sys; "
        f"sys.path.insert(0, {str(APP)!r}); "
        "from PySide6.QtWidgets import QApplication; "
        "app = QApplication([]); "
        "import ui.main_window; "
        "heavy = [m for m in ('core.engine', 'pandas', 'numpy', 'torch') "
        "if m in sys.modules]; "
        "assert not heavy, heavy"
    )
    assert result.returncode == 0, result.stderr


def test_rejected_consent_exits_before_main_window_and_event_loop():
    result = _offscreen_python(r'''
import importlib.util, os, sys
from pathlib import Path
ROOT = Path(os.environ["SAMT_PROJECT_ROOT"])
calls = []
class QApplication:
    def __new__(cls, *args):
        return type("A", (), {
            "setApplicationName": lambda *a: None,
            "setApplicationVersion": lambda self, v: calls.append(
                ("version", v)),
            "setFont": lambda *a: None,
            "setPalette": lambda *a: None,
            "setStyleSheet": lambda *a: None,
            "setAttribute": lambda *a: None,
            "exec": lambda self: calls.append("eventloop"),
        })()
qt_widgets = type(sys)("PySide6.QtWidgets")
qt_widgets.QApplication = QApplication
qt_widgets.QDialog = type("QDialog", (), {"Accepted": 1, "Rejected": 0})
qt_core = type(sys)("PySide6.QtCore")
qt_core.Qt = type("Qt", (), {"AA_DontShowIconsInMenus": 0})
qt_gui = type(sys)("PySide6.QtGui")
qt = type(sys)("PySide6")
qt.QtCore, qt.QtGui, qt.QtWidgets = qt_core, qt_gui, qt_widgets
sys.modules.update({"PySide6": qt, "PySide6.QtCore": qt_core,
                    "PySide6.QtGui": qt_gui,
                    "PySide6.QtWidgets": qt_widgets})
i18n_mod = type(sys)("i18n")
i18n_mod.I18n = lambda lang: type("I", (), {"lang": lang})()
settings_mod = type(sys)("settings")
settings_mod.Settings = lambda: type("S", (), {"data": {
    "language": "en-US", "disclaimer_accepted": False}})()
theme_mod = type(sys)("ui.theme")
theme_mod.application_font = lambda: None
theme_mod.palette = lambda: None
theme_mod.stylesheet = lambda: ""
ui_mod = type(sys)("ui.main_window")
ui_mod.MainWindow = lambda: (_ for _ in ()).throw(
    AssertionError("main window constructed"))
ui_mod.ResearchUseGate = lambda *a: type("G", (), {
    "exec": lambda self: (calls.append("gate"), 0)[1]})()
ui_mod.has_current_consent = lambda s: False
sys.modules.update({"i18n": i18n_mod, "settings": settings_mod,
                    "ui.theme": theme_mod, "ui.main_window": ui_mod})
spec = importlib.util.spec_from_file_location(
    "samt_entry", ROOT / "app" / "main.py")
entry = importlib.util.module_from_spec(spec)
sys.modules["samt_entry"] = entry
spec.loader.exec_module(entry)
assert entry.main() == 0
assert ("version", "1.3.0") in calls
assert "gate" in calls and "eventloop" not in calls
assert not [m for m in ("core.engine", "pandas", "numpy", "torch", "PIL")
            if m in sys.modules]
''')
    assert result.returncode == 0, result.stderr


def test_image_preview_import_is_lightweight_and_qt_safe(tmp_path):
    snippet = "\n".join((
        "import sys",
        f"sys.path.insert(0, {str(APP)!r})",
        "import ui.image_preview as preview",
        "assert 'numpy' not in sys.modules",
        "assert 'SimpleITK' not in sys.modules",
        "try:",
        "    preview.preview_pixmap('/missing.nii.gz')",
        "except preview.ImagePreviewError as exc:",
        "    assert 'file' in str(exc) or 'qt' in str(exc)",
        "else:",
        "    raise AssertionError('missing file not rejected')",
    ))
    result = _offscreen_python(snippet)
    assert result.returncode == 0, result.stderr


def test_preview_renders_a_real_nifti_with_qt_application(tmp_path):
    import SimpleITK as sitk
    import numpy as np

    path = tmp_path / "slice.nii.gz"
    volume = np.arange(4 * 9 * 7, dtype=np.float32).reshape((4, 9, 7))
    sitk.WriteImage(sitk.GetImageFromArray(volume), str(path))
    result = _offscreen_python(
        "import sys; "
        f"sys.path.insert(0, {str(APP)!r}); "
        "from PySide6.QtWidgets import QApplication; "
        "from ui.image_preview import preview_pixmap; "
        "app = QApplication([]); "
        f"pixmap, shape = preview_pixmap({str(path)!r}, 60); "
        "assert pixmap.width() == 60; "
        "assert shape == '4 × 9 × 7'"
    )
    assert result.returncode == 0, result.stderr


def test_dynamic_status_messages_switch_language_without_restart():
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    MainWindow._prepare_engine = lambda self: None
    window = MainWindow()
    window.i18n.set_language("en-US")
    window._apply_language("en-US")
    window._set_status(window.batch_status, "batch.scan_problems",
                       problems="missing:MRMG")
    assert window.batch_status.text().startswith("Directory validation:")
    window._apply_language("zh-CN")
    assert window.batch_status.text().startswith("目录校验：")
    window.close()


def test_consent_once_is_persisted_and_unchecked_reminder_asks_again():
    from PySide6.QtWidgets import QApplication
    from i18n import I18n
    from ui.main_window import ResearchUseGate, has_current_consent

    app = QApplication.instance() or QApplication([])
    saved = []
    settings = type("S", (), {
        "data": {"language": "en-US"},
        "save": lambda self: saved.append(dict(self.data)),
    })()
    gate = ResearchUseGate(I18n("en-US"), settings)
    assert not gate.enter_btn.isEnabled()
    gate.checkbox.setChecked(True)
    assert gate.enter_btn.isEnabled()
    gate.accept()
    assert has_current_consent(settings)

    dismiss_each_time = type("S", (), {
        "data": {"language": "en-US"},
        "save": lambda self: None,
    })()
    gate = ResearchUseGate(I18n("en-US"), dismiss_each_time)
    gate.checkbox.setChecked(True)
    gate.hide_reminder.setChecked(False)
    gate.accept()
    assert not has_current_consent(dismiss_each_time)

    legacy = type("S", (), {"data": {
        "disclaimer_accepted": True,
        "accepted_disclaimer_version": "1.2.0",
    }})()
    assert not has_current_consent(legacy)
    upgraded = type("S", (), {"data": {
        "disclaimer_accepted": True,
        "accepted_disclaimer_version": "1.3.0",
    }})()
    assert has_current_consent(upgraded)


def test_selected_case_directory_scans_only_that_case(tmp_path):
    from PySide6.QtWidgets import QApplication
    from core.experiment_contract import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    MainWindow._prepare_engine = lambda self: None
    root = tmp_path / "CohortA"
    for label, case_id in (("Negative", "patient_A"),
                           ("Positive", "patient_B")):
        case = root / "MRMG" / label / case_id
        (case / "MG").mkdir(parents=True)
        for name in (
            f"{case_id}_DCE_N4.nii.gz", f"{case_id}_DCE_decay1.nii.gz",
            f"MG/{case_id}_MG_MLO.nii.gz",
            f"MG/{case_id}_MLO_decay1.nii.gz",
        ):
            (case / name).write_bytes(b"test")
    rows = []
    for case_id in ("patient_A", "patient_B"):
        row = {column: "0" for column in
               CLINICAL_COLUMNS + PATHOLOGY_COLUMNS}
        row["ID"] = case_id
        rows.append(row)
    pd.DataFrame(rows).to_excel(root / "CP.xlsx",
                                sheet_name="Sheet1", index=False)

    window = MainWindow()
    selected = root / "MRMG" / "Positive" / "patient_B"
    window.batch_dir_edit.setText(str(selected))
    window.scan_batch()
    assert [case.case_id for case in window.batch_cases] == ["patient_B"]
    assert window.batch_status.text()
    window.close()


def test_locale_catalogs_have_matching_keys_and_runtime_terms():
    catalogs = {}
    for code in ("en-US", "zh-CN"):
        catalogs[code] = json.loads(
            (APP / "locales" / f"{code}.json").read_text("utf-8"))
    assert set(catalogs["en-US"]) == set(catalogs["zh-CN"])
    required = (
        "common.filter.nifti", "common.filter.excel", "common.filter.csv",
        "common.export_csv", "clinical.error.unreadable",
        "clinical.error.missing_id", "clinical.error.missing_columns",
        "clinical.error.case_id_required", "clinical.error.no_row",
        "clinical.error.ambiguous", "inputs.dce_n4",
        "inputs.dce_decay1", "inputs.mlo", "inputs.mlo_decay1",
    )
    for key in required:
        assert key in catalogs["en-US"]
        assert catalogs["en-US"][key] != key
        assert catalogs["zh-CN"][key] != key

    # No locale catalog may fall back to another language's prose.
    import re

    for key, text in catalogs["en-US"].items():
        if key == "common.language_zh":
            continue
        assert not re.search(r"[\u4e00-\u9fff]", text), (key, text)
    technical = (
            "SAMT", "DCE", "MLO", "N4", "decay", "CPU", "CUDA", "MPS",
            "MRI",
        "CP.xlsx", "MRMG", "Positive", "Negative", "NSLN", "ER", "PR",
        "HER2", "Ki67", "ALN", "SLN", "ID", "CSV", "AUC", "ACC",
            "softmax", "NIfTI", "CaseID", "ResNet", "Transformer", "MLP",
            "Dataset", "CLS",
        "tokens", "logits", "P(NSLN", "P(negative", "P(positive",
            ".csv", ".nii", ".xlsx", ".xlsm", ".gz", "nii", "root", "MRMG",
            "Excel", "xlsx", "xlsm",
        "CP.xlsx", "Positive", "Negative", "CaseID", "Sheet",
    )
    placeholders = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*(?::[^}]*)?\}")
    for key, text in catalogs["zh-CN"].items():
        if key == "common.language_en":
            continue
        text = placeholders.sub("", text)
        for phrase in re.findall(r"[A-Za-z][A-Za-z\s,.()/;:-]{3,}", text):
            assert any(term in phrase for term in technical), \
                (key, phrase)
