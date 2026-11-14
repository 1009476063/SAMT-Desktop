"""v1.4.0 source-image preparation and critical-result regressions."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _write_nifti(path: Path, array, dtype=np.float32):
    import SimpleITK as sitk

    path.parent.mkdir(parents=True, exist_ok=True)
    image = sitk.GetImageFromArray(array.astype(dtype))
    image.SetSpacing((1.0, 1.0, 1.0) if array.ndim == 3 else (1.0, 1.0))
    sitk.WriteImage(image, str(path))
    return path


def test_decay_formulas_match_experiment_implementation(tmp_path):
    import importlib.util
    from core.preprocessing import create_dce_decay, create_mlo_decay

    source = (ROOT.parent / "同步空间" / "TanXiang" / "SAMT" /
              "src" / "get_SAmask.py")
    if not source.is_file():
        source = Path("/Users/tanxiang/同步空间/TanXiang/SAMT/src/get_SAmask.py")
    if not source.is_file():
        pytest.skip("original experiment source unavailable")
    spec = importlib.util.spec_from_file_location("experiment_samask", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    mask1 = np.zeros((6, 7, 8), dtype=np.float32)
    mask2 = np.zeros_like(mask1)
    mask1[2, 3, 4] = 1
    mask2[4, 4, 5] = 1
    path1 = _write_nifti(tmp_path / "DCE_GTV.nii.gz", mask1)
    path2 = _write_nifti(tmp_path / "DCE_GTVnd1.nii.gz", mask2)
    expected_dce = module.create_decay_mask_adaptive(
        mask1, mask2, sigma_base=3.0)
    actual_dce = create_dce_decay(path1, path2, tmp_path / "dce.nii.gz")
    import nibabel as nib

    dce_array = nib.load(str(actual_dce)).get_fdata()
    assert dce_array.shape == expected_dce.shape[::-1]
    assert np.array_equal(
        dce_array,
        np.asarray(expected_dce, dtype=np.float16).transpose(2, 1, 0))

    mlo1 = np.zeros((8, 9), dtype=np.float32)
    mlo2 = np.zeros_like(mlo1)
    mlo1[3, 3] = 1
    mlo2[5, 6] = 1
    path3 = _write_nifti(tmp_path / "MLO_GTV.nii.gz", mlo1)
    path4 = _write_nifti(tmp_path / "MLO_GTVnd1.nii.gz", mlo2)
    expected_mlo, _ = module.create_linear_decay_adaptive(
        mlo1, mlo2, distance_factor=3.0)
    actual_mlo = create_mlo_decay(path3, path4, tmp_path / "mlo.nii.gz")
    mlo_array = nib.load(str(actual_mlo)).get_fdata()
    assert mlo_array.shape == expected_mlo.shape[::-1]
    assert np.array_equal(mlo_array, np.round(expected_mlo, 4).astype(
        np.float32).transpose(1, 0))


def test_prepare_case_inputs_generates_three_offline_products(tmp_path):
    from core.preprocessing import prepare_case_inputs

    root = tmp_path / "case1"
    volume = np.arange(4 * 5 * 6, dtype=np.float32).reshape((4, 5, 6))
    _write_nifti(root / "case1_DCE.nii.gz", volume)
    contour = np.zeros((4, 5, 6), dtype=np.float32)
    contour[1:3, 2:4, 3] = 1
    _write_nifti(root / "case1_DCE_GTV.nii.gz", contour)
    _write_nifti(root / "case1_DCE_GTVnd1.nii.gz", contour)
    mlo = np.arange(30, dtype=np.float32).reshape((5, 6))
    _write_nifti(root / "MG" / "case1_MG_MLO.nii.gz", mlo)
    mlo_contour = np.zeros((5, 6), dtype=np.float32)
    mlo_contour[2, 3] = 1
    _write_nifti(root / "MG" / "case1_MG_LMLO_GTV.nii.gz", mlo_contour)
    _write_nifti(root / "MG" / "case1_MG_LMLO_GTVnd1.nii.gz", mlo_contour)

    prepared = prepare_case_inputs(root, "case1", output_root=tmp_path / "derived")

    assert prepared.complete
    assert prepared.generated == (
        "DCE_N4", "DCE_decay1", "MLO_decay1")
    assert all(path.is_file() for path in prepared.model_inputs.values())
    assert not (root / "case1_DCE_N4.nii.gz").exists()
    assert prepared.dce_n4.name == "case1_DCE_N4.nii.gz"
    assert prepared.dce_decay.name == "case1_DCE_decay1.nii.gz"
    assert prepared.mlo_decay.name == "case1_MLO_decay1.nii.gz"

    from core.preprocessing import find_source_inputs

    found_again = find_source_inputs(root, "case1")
    assert found_again.dce_n4 is None
    assert found_again.dce_decay is None


def test_trailing_singleton_mlo_contours_match_experiment(tmp_path):
    import importlib.util
    import nibabel as nib
    from core.preprocessing import create_mlo_decay

    source = (ROOT.parent / "同步空间" / "TanXiang" / "SAMT" /
              "src" / "get_SAmask.py")
    if not source.is_file():
        source = Path("/Users/tanxiang/同步空间/TanXiang/SAMT/src/get_SAmask.py")
    if not source.is_file():
        pytest.skip("original experiment source unavailable")
    spec = importlib.util.spec_from_file_location("experiment_samask", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    mask1 = np.zeros((8, 9, 1), dtype=np.float32)
    mask2 = np.zeros_like(mask1)
    mask1[3, 3, 0] = 1
    mask2[5, 6, 0] = 1
    path1 = _write_nifti(tmp_path / "MLO_GTV.nii.gz", mask1)
    path2 = _write_nifti(tmp_path / "MLO_GTVnd1.nii.gz", mask2)
    expected, _ = module.create_linear_decay_adaptive(mask1, mask2)
    expected = np.round(np.clip(expected, 0, 1), 4).astype(np.float32)

    actual = create_mlo_decay(path1, path2, tmp_path / "mlo.nii.gz")
    array = nib.load(str(actual)).get_fdata()

    assert array.shape == (1, 9, 8)
    assert np.array_equal(array, expected.transpose(2, 1, 0))


def test_derived_products_in_case_root_do_not_masquerade_as_supplied(tmp_path):
    from core.preprocessing import prepare_case_inputs

    root = tmp_path / "case2"
    (root / "MG").mkdir(parents=True)
    files = {
        "DCE_N4": root / "case2_DCE_N4.nii.gz",
        "DCE_decay1": root / "case2_DCE_decay1.nii.gz",
        "MLO": root / "MG" / "case2_MG_MLO.nii.gz",
        "MLO_decay1": root / "MG" / "case2_MLO_decay1.nii.gz",
    }
    for name, path in files.items():
        path.write_bytes(("original-" + name).encode("ascii"))

    prepared = prepare_case_inputs(root, "case2")

    assert prepared.complete
    assert prepared.generated == ()
    assert all(path.read_bytes().startswith(b"original-")
               for path in files.values())


def test_in_place_derived_inputs_are_not_mistaken_for_supplied_products(
        tmp_path):
    from core.preprocessing import prepare_case_inputs

    root = tmp_path / "case3"
    volume = np.arange(3 * 4 * 5, dtype=np.float32).reshape((3, 4, 5))
    _write_nifti(root / "case3_DCE.nii.gz", volume)
    contour = np.zeros((3, 4, 5), dtype=np.float32)
    contour[1, 2, 2] = 1
    _write_nifti(root / "case3_DCE_GTV.nii.gz", contour)
    _write_nifti(root / "case3_DCE_GTVnd1.nii.gz", contour)
    mlo = np.arange(12, dtype=np.float32).reshape((3, 4))
    _write_nifti(root / "MG" / "case3_MG_MLO.nii.gz", mlo)
    mlo_contour = np.zeros((3, 4), dtype=np.float32)
    mlo_contour[1, 1] = 1
    _write_nifti(root / "MG" / "case3_MG_LMLO_GTV.nii.gz", mlo_contour)
    _write_nifti(root / "MG" / "case3_MG_LMLO_GTVnd1.nii.gz", mlo_contour)

    first = prepare_case_inputs(root, "case3")
    second = prepare_case_inputs(root, "case3")

    assert first.generated == ("DCE_N4", "DCE_decay1", "MLO_decay1")
    assert second.generated == ()
    assert second.dce_n4 == first.dce_n4
    assert second.dce_decay == first.dce_decay
    assert second.mlo_decay == first.mlo_decay


def test_default_form_is_empty_and_critical_probability_is_explicit(
        qt_app, monkeypatch):
    from PySide6.QtWidgets import QApplication, QComboBox
    from core.engine import ScanResult
    from ui.main_window import MainWindow

    settings = type("S", (), {
        "data": {"language": "en-US"},
        "save": lambda self: None,
    })()
    import ui.main_window as main_window

    monkeypatch.setattr(main_window, "Settings", lambda: settings)
    monkeypatch.setattr(MainWindow, "_prepare_engine", lambda self: None)
    window = MainWindow()
    for widget in window.form_edits.values():
        if isinstance(widget, QComboBox):
            assert widget.currentData() == ""
        else:
            assert widget.text() == ""

    folds = {}
    for index in range(10):
        folds["fold_{}".format(index)] = (
            [0.1, 0.9] if index < 5 else [0.9, 0.1])
    result = ScanResult("case1", 0.491009, 0.508991, "Positive", folds)
    window._show_single_result(result)
    assert "0.508991" in window.positive_prob.text()
    assert "5 positive / 5 negative" in window.single_criticality.text()
    assert "0.008991" in window.single_criticality.text()
    window.close()


def test_form_controls_fit_and_switch_to_stacked_at_narrow_width(
        qt_app, monkeypatch):
    from PySide6.QtWidgets import QApplication, QComboBox
    from ui.main_window import MainWindow
    import ui.main_window as main_window

    settings = type("S", (), {
        "data": {"language": "en-US"},
        "save": lambda self: None,
    })()
    monkeypatch.setattr(main_window, "Settings", lambda: settings)
    monkeypatch.setattr(MainWindow, "_prepare_engine", lambda self: None)
    window = MainWindow()
    window.resize(1180, 760)
    window.show()
    QApplication.processEvents()
    window._sync_single_layout()
    QApplication.processEvents()

    assert window._single_stacked is True
    scroll = window.pages.widget(1)
    assert scroll.widget().width() <= scroll.viewport().width()
    combo = next(widget for widget in window.form_edits.values()
                 if isinstance(widget, QComboBox))
    assert combo.currentText() == "Select…"
    assert combo.minimumSizeHint().width() < 280
    window.close()


def test_prepare_batch_makes_raw_source_directory_runnable(
        qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication
    from core.experiment_contract import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS
    from ui.main_window import MainWindow
    import ui.main_window as main_window

    root = tmp_path / "Study"
    case = root / "MRMG" / "Unknown" / "raw_case"
    (case / "MG").mkdir(parents=True)
    volume = np.arange(3 * 4 * 5, dtype=np.float32).reshape((3, 4, 5))
    _write_nifti(case / "raw_case_DCE.nii.gz", volume)
    contour = np.zeros((3, 4, 5), dtype=np.float32)
    contour[1, 2, 2] = 1
    _write_nifti(case / "raw_case_DCE_GTV.nii.gz", contour)
    _write_nifti(case / "raw_case_DCE_GTVnd1.nii.gz", contour)
    mlo = np.arange(12, dtype=np.float32).reshape((3, 4))
    _write_nifti(case / "MG" / "raw_case_MG_MLO.nii.gz", mlo)
    mlo_contour = np.zeros((3, 4), dtype=np.float32)
    mlo_contour[1, 1] = 1
    _write_nifti(case / "MG" / "raw_case_MG_LMLO_GTV.nii.gz", mlo_contour)
    _write_nifti(case / "MG" /
                 "raw_case_MG_LMLO_GTVnd1.nii.gz", mlo_contour)
    row = {"ID": "raw_case"}
    row.update({column: "0" for column in
                CLINICAL_COLUMNS + PATHOLOGY_COLUMNS})
    pd.DataFrame([row]).to_excel(
        root / "CP.xlsx", sheet_name="Sheet1", index=False)

    settings = type("S", (), {
        "data": {"language": "en-US"},
        "save": lambda self: None,
    })()
    monkeypatch.setattr(main_window, "Settings", lambda: settings)
    monkeypatch.setattr(MainWindow, "_prepare_engine", lambda self: None)
    window = MainWindow()
    window.batch_dir_edit.setText(str(root))
    window.preprocess_dir_edit.setText(str(root))
    window.engine = type("Engine", (), {
        "checkpoint_count": 10,
        "cleanup": lambda self: None,
    })()
    window.prepare_batch()
    if window._prepare_thread is not None:
        window._prepare_thread.wait(30000)
        QApplication.processEvents()

    assert len(window.batch_cases) == 1
    assert window.batch_cases[0].dce_n4.is_file()
    assert window.batch_cases[0].dce_decay.is_file()
    assert window.batch_cases[0].mlo_decay.is_file()
    assert window.batch_table.item(0, 3).text() == "Ready"
    assert window.batch_run_btn.isEnabled()
    window.close()


def test_clinical_diameter_is_derived_exactly_and_source_is_untouched(tmp_path):
    from core.experiment_contract import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS
    from core.preprocessing import (
        ALN_DIAMETER_COLUMN, lowest_layer_aln_diameter, prepare_clinical_table,
    )

    root = tmp_path / "Study"
    case = root / "MRMG" / "Negative" / "case1"
    case.mkdir(parents=True)
    contour = np.zeros((3, 8, 10), dtype=np.float32)
    contour[0, 1, 2] = 1
    contour[0, 5, 8] = 1
    path = _write_nifti(case / "case1_DCE_GTVnd1.nii.gz", contour)
    expected = lowest_layer_aln_diameter(path)
    columns = ["ID"] + CLINICAL_COLUMNS + PATHOLOGY_COLUMNS
    rows = [
        {column: "" for column in columns} | {"ID": "case1"},
        {column: "" for column in columns} | {
            "ID": "case2", ALN_DIAMETER_COLUMN: 12.34},
    ]
    source = root / "CP.xlsx"
    pd.DataFrame(rows).to_excel(source, sheet_name="Sheet1", index=False)
    original = source.read_bytes()
    staged = tmp_path / "staged" / "CP.xlsx"

    table, count = prepare_clinical_table(root, staged)

    assert table == staged and count == 1
    assert source.read_bytes() == original
    frame = pd.read_excel(staged, sheet_name="Sheet1")
    assert frame.loc[0, ALN_DIAMETER_COLUMN] == expected
    assert frame.loc[1, ALN_DIAMETER_COLUMN] == 12.34
    assert expected == 7.21


def test_prepare_incomplete_errors_are_fully_localized():
    import json
    from core.experiment_contract import localized_problem
    from i18n import I18n

    catalogs = {
        code: json.loads(
            (APP / "locales" / "{}.json".format(code)).read_text("utf-8"))
        for code in ("en-US", "zh-CN")
    }
    for code, catalog in catalogs.items():
        i18n = I18n(code)
        for source in ("source.dce", "source.mlo"):
            text = localized_problem(
                i18n, "prepare.incomplete:case1:" + source)
            assert text == catalog["prepare.incomplete"].format(
                detail="case1", names=catalog[source])
            assert "source.source." not in text


def test_staging_prefers_one_derived_clinical_workbook(tmp_path):
    from core.engine import InferenceEngine, PatientCase
    from core.experiment_contract import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS

    source = tmp_path / "case1"
    (source / "MG").mkdir(parents=True)
    for relative in (
        "case1_DCE_N4.nii.gz", "case1_DCE_decay1.nii.gz",
        "MG/case1_MG_MLO.nii.gz", "MG/case1_MLO_decay1.nii.gz",
    ):
        (source / relative).write_bytes(b"image")
    table = tmp_path / "derived.xlsx"
    columns = ["ID"] + CLINICAL_COLUMNS + PATHOLOGY_COLUMNS
    row = {column: "0" for column in columns}
    row["ID"] = "case1"
    row["max diameter with lowest layer of ALN"] = 38.6
    pd.DataFrame([row]).to_excel(table, sheet_name="Sheet1", index=False)
    case = PatientCase(
        "case1", "Negative", source, {"ID": "case1"},
        clinical_table=table, dce_n4=source / "case1_DCE_N4.nii.gz",
        dce_decay=source / "case1_DCE_decay1.nii.gz",
        mlo=source / "MG" / "case1_MG_MLO.nii.gz",
        mlo_decay=source / "MG" / "case1_MLO_decay1.nii.gz")
    engine = InferenceEngine.__new__(InferenceEngine)
    engine._scratch = tmp_path / "scratch"
    engine._scratch.mkdir()

    root = engine.stage_cases([case])
    staged = pd.read_excel(root / "CP.xlsx", sheet_name="Sheet1")

    assert staged.loc[0, "max diameter with lowest layer of ALN"] == 38.6


def test_critical_dataframe_keeps_vote_split_and_margin():
    from core.engine import ScanResult, scan_results_to_dataframe

    folds = {}
    for index in range(10):
        folds["fold_{}".format(index)] = (
            [0.1, 0.9] if index < 5 else [0.9, 0.1])
    result = ScanResult("case1", 0.491009, 0.508991, "Positive", folds)

    row = scan_results_to_dataframe([result]).iloc[0]

    assert row["P(Positive)"] == 0.508991
    assert row["Positive_folds"] == 5
    assert row["Negative_folds"] == 5
    assert row["Margin_from_0.5"] == 0.008991
