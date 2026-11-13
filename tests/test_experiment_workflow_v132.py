"""Regression checks for the v1.3.2 experiment workflow."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


class _MemorySettings:
    def __init__(self, data=None):
        self.data = {
            "language": "en-US",
            "last_data_dir": "/private/operator/path",
            **(data or {}),
        }
        self.saved = 0

    def save(self):
        self.saved += 1


class _FakeEngine:
    def __init__(self, checkpoint_count=10):
        self.checkpoint_count = checkpoint_count

    def cleanup(self):
        return None


class _Signal:
    def __init__(self):
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def disconnect(self):
        self.slots.clear()


class _DeferredInferenceThread:
    def __init__(self, engine, cases, parent=None):
        self.engine = engine
        self.cases = cases
        self.progress_text = _Signal()
        self.finished_ok = _Signal()
        self.failed = _Signal()
        self.started = False

    def start(self):
        self.started = True

    def isRunning(self):
        return False

    def wait(self, *_args):
        return True

    def deleteLater(self):
        return None


@pytest.fixture(scope="module")
def qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _window(monkeypatch, settings):
    import ui.main_window as main_window

    monkeypatch.setattr(main_window, "Settings", lambda: settings)
    monkeypatch.setattr(main_window.MainWindow, "_prepare_engine",
                        lambda self: None)
    return main_window, main_window.MainWindow()


def test_batch_starts_empty_and_selected_directory_is_session_only(
        qt_app, monkeypatch, tmp_path):
    import ui.main_window as main_window

    settings = _MemorySettings()
    _, window = _window(monkeypatch, settings)
    selected = tmp_path / "operator-selected-cohort"
    selected.mkdir()

    assert window.batch_dir_edit.text() == ""
    monkeypatch.setattr(
        main_window.QFileDialog, "getExistingDirectory",
        lambda *_args, **_kwargs: str(selected),
    )
    window._pick_data_dir()

    assert window.batch_dir_edit.text() == str(selected)
    assert "last_data_dir" not in settings.data
    window.close()


def test_batch_begin_and_fold_signals_drive_visible_percent_progress(
        qt_app, monkeypatch):
    import ui.main_window as main_window

    settings = _MemorySettings()
    main_window, window = _window(monkeypatch, settings)
    monkeypatch.setattr(main_window, "InferThread",
                        _DeferredInferenceThread)
    window.engine = _FakeEngine()
    cases = [
        SimpleNamespace(case_id="patient_A"),
        SimpleNamespace(case_id="patient_B"),
    ]

    window._begin_inference(cases, single=False)

    assert window._active_thread.started
    assert "2" in window.batch_status.text()
    assert window.batch_progress.text() == "0%"
    assert window.batch_progress.format() == "%p%"

    window._on_infer_progress("preprocess:patient_A")
    for fold in range(10):
        window._on_infer_progress("fold:fold_{}".format(fold))
    window._on_infer_progress("case:patient_A:1:2")
    assert window.batch_progress.value() == 50
    assert window.batch_progress.text() == "50%"

    window._busy = False
    window.close()


def test_completed_batch_renders_results_and_enables_csv(
        qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QPushButton, QTableWidgetItem
    from core.engine import PatientCase, ScanResult
    from core.experiment_contract import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS

    settings = _MemorySettings()
    _, window = _window(monkeypatch, settings)
    case_root = tmp_path / "Study" / "MRMG" / "Positive" / "patient_D"
    (case_root / "MG").mkdir(parents=True)
    for relative in (
        "patient_D_DCE_N4.nii.gz",
        "patient_D_DCE_decay1.nii.gz",
        "MG/patient_D_MG_MLO.nii.gz",
        "MG/patient_D_MLO_decay1.nii.gz",
    ):
        (case_root / relative).write_bytes(b"synthetic")
    table_row = {"ID": "patient_D"}
    table_row.update({column: "0" for column in
                      CLINICAL_COLUMNS + PATHOLOGY_COLUMNS})
    case = PatientCase("patient_D", "Positive", case_root, table_row)
    fold_probs = {
        "fold_{}".format(index): [0.1865429889, 0.8134570181]
        for index in range(10)
    }
    result = ScanResult(
        "patient_D", 0.1865429889, 0.8134570181, "Positive", fold_probs)

    window.engine = _FakeEngine()
    window.batch_cases = [case]
    window._case_rows = [SimpleNamespace(
        case_id="patient_D", label_dir="Positive",
        case_root=case_root, missing=())]
    window.batch_table.setRowCount(1)
    window.batch_table.setItem(0, 0, QTableWidgetItem("patient_D"))
    window._refresh_batch_rows()
    window._dispose_active_thread = lambda: None
    window._inference_done([result], single=False)

    assert window._last_df is not None
    assert len(window._last_df) == 1
    assert window.batch_export_btn.isEnabled()
    assert window.batch_table.item(0, 4).text() == "0.186543"
    assert window.batch_table.item(0, 5).text() == "0.813457"
    assert window.batch_table.item(0, 6).text() == "Positive"
    assert isinstance(window.batch_table.cellWidget(0, 7), QPushButton)
    assert window.batch_summary_prediction.text() == "Positive"
    assert "0.813457" in window.batch_summary_positive.text()

    window._apply_language("zh-CN")
    assert window.batch_table.item(0, 6).text() == "阳性"
    assert window.batch_table.horizontalHeaderItem(4).text() == "P(阴性)"
    assert window.batch_summary_prediction.text() == "阳性"
    window.close()


def test_volume_viewer_loads_nifti_and_browses_three_planes(
        qt_app, tmp_path):
    import SimpleITK as sitk
    from i18n import I18n
    from ui.image_viewer import ImageVolumeViewer

    volume = np.arange(4 * 9 * 7, dtype=np.float32).reshape((4, 9, 7))
    path = tmp_path / "volume.nii.gz"
    sitk.WriteImage(sitk.GetImageFromArray(volume), str(path))

    viewer = ImageVolumeViewer(
        I18n("en-US"), {"DCE-MRI": path}, initial_key="DCE-MRI")

    assert viewer.volume_shape == (4, 9, 7)
    assert viewer.current_plane().shape == (9, 7)
    viewer.set_orientation("coronal")
    assert viewer.current_plane().shape == (4, 7)
    viewer.slice_slider.setValue(2)
    assert viewer.slice_index() == 2
    viewer.set_orientation("sagittal")
    assert viewer.current_plane().shape == (4, 9)
    assert viewer.slice_slider.maximum() == 6
    viewer.close()


def test_volume_viewer_accepts_two_dimensional_mammography(
        qt_app, tmp_path):
    import SimpleITK as sitk
    from i18n import I18n
    from ui.image_viewer import ImageVolumeViewer

    image = np.arange(8 * 11, dtype=np.float32).reshape((8, 11))
    path = tmp_path / "mlo.nii.gz"
    sitk.WriteImage(sitk.GetImageFromArray(image), str(path))

    viewer = ImageVolumeViewer(I18n("en-US"), {"MLO": path})

    assert viewer.volume_shape == (8, 11)
    assert viewer.current_plane().shape == (8, 11)
    assert viewer.slice_slider.maximum() == 0
    viewer.close()


def test_single_inline_viewer_reuses_decoded_volume_when_stepping(
        qt_app, monkeypatch, tmp_path):
    import SimpleITK as sitk
    import ui.image_preview as image_preview

    volume = np.arange(5 * 8 * 9, dtype=np.float32).reshape((5, 8, 9))
    path = tmp_path / "inline.nii.gz"
    sitk.WriteImage(sitk.GetImageFromArray(volume), str(path))
    settings = _MemorySettings()
    _, window = _window(monkeypatch, settings)
    window.file_edits["dce_n4"].setText(str(path))
    reads = []
    original = image_preview.read_volume

    def counted(source):
        reads.append(str(source))
        return original(source)

    monkeypatch.setattr(image_preview, "read_volume", counted)
    window._update_single_viewer()
    window.single_slice_slider.setValue(3)
    window.single_plane_combo.setCurrentIndex(
        window.single_plane_combo.findData("coronal"))
    window.single_slice_slider.setValue(1)

    assert len(reads) == 1
    window.close()
