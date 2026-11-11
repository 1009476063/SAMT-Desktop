"""Static and numerical guards around the experiment inference contract."""
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from core.engine import (  # noqa: E402
    CLINICAL_COLUMNS, PATHOLOGY_COLUMNS, InferenceEngine, ScanResult,
    scan_results_to_dataframe,
)


def test_feature_contract_has_55_source_columns():
    assert len(CLINICAL_COLUMNS) == 9
    assert len(PATHOLOGY_COLUMNS) == 10
    assert "Laterality " in CLINICAL_COLUMNS
    assert "Positive_Total_SLN_ratio" in PATHOLOGY_COLUMNS


def test_checkpoint_discovery_excludes_backbone_weights(tmp_path):
    (tmp_path / "pathology_pretrain_fold1_best_AUC_val.pth").touch()
    (tmp_path / "resnet_18_23dataset.pth").touch()
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.models_dir = tmp_path
    engine._ckpt_paths = engine._discover_checkpoints()
    assert [p.name for p in engine._ckpt_paths] == [
        "pathology_pretrain_fold1_best_AUC_val.pth"
    ]


def test_ensemble_mean_and_prediction():
    engine = InferenceEngine.__new__(InferenceEngine)
    engine.retain_checkpoints = True
    engine._on_status = None
    scan = ScanResult(
        "c1", 0.4, 0.6, "Positive",
        {"a": [0.3, 0.7], "b": [0.5, 0.5]},
    )
    df = scan_results_to_dataframe([scan], {"c1": "Positive"})
    assert df.loc[0, "P(Negative)"] == 0.4
    assert df.loc[0, "P(Positive)"] == 0.6
    assert df.loc[0, "Ensemble_N"] == 2


def test_reference_device_is_cpu():
    engine = InferenceEngine.__new__(InferenceEngine)
    torch = __import__("types").SimpleNamespace(
        cuda=__import__("types").SimpleNamespace(is_available=lambda: True),
        backends=__import__("types").SimpleNamespace(
            mps=__import__("types").SimpleNamespace(is_available=lambda: True)),
    )
    assert engine.default_device(torch) == "cpu"
    assert engine.available_devices(torch) == ["cpu", "cuda", "mps"]


def test_staging_only_links_four_model_inputs(tmp_path):
    source = tmp_path / "case1"
    (source / "MG").mkdir(parents=True)
    names = [
        "case1_DCE_N4.nii.gz", "case1_DCE_decay1.nii.gz",
        "case1_DCE_GTV.nii.gz", "case1_unrelated.nii.gz",
        "MG/case1_MG_MLO.nii.gz", "MG/case1_MLO_decay1.nii.gz",
        "MG/case1_MG_MLO_GTV.nii.gz",
    ]
    for name in names:
        (source / name).write_bytes(b"test")
    row = {column: "0" for column in CLINICAL_COLUMNS + PATHOLOGY_COLUMNS}
    row["ID"] = "case1"
    case = type("Case", (), {
        "case_id": "case1", "label_dir": "Negative",
        "case_root": source, "table_row": row,
    })()
    engine = InferenceEngine.__new__(InferenceEngine)
    engine._scratch = tmp_path / "scratch"
    engine._scratch.mkdir()
    root = engine.stage_cases([case])
    staged = sorted(
        str(p.relative_to(root / "MRMG")) for p in
        (root / "MRMG").rglob("*.nii.gz")
    )
    assert staged == [
        "Negative/case1/MG/case1_MG_MLO.nii.gz",
        "Negative/case1/MG/case1_MLO_decay1.nii.gz",
        "Negative/case1/case1_DCE_N4.nii.gz",
        "Negative/case1/case1_DCE_decay1.nii.gz",
    ]
    assert (root / "CP.xlsx").is_file()
