import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from core.engine import (  # noqa: E402
    PatientCase, discover_cases, validate_case, InferenceEngine,
)


def _sample_root() -> Path:
    configured = os.environ.get("SAMT_SAMPLE_ROOT", "").strip()
    return Path(configured) if configured else None


def test_discover_sample_tree():
    root = _sample_root()
    if root is None or not root.is_dir():
        return  # sample data not available; discovery logic is covered elsewhere
    cases, problems = discover_cases(root)
    assert problems == []
    assert {c.case_id for c in cases} == {"case1", "case2"}
    for c in cases:
        assert validate_case(c) == []


def test_validate_missing_columns():
    case = PatientCase(case_id="x", label_dir="Positive", case_root=Path("."), table_row={})
    problems = validate_case(case)
    assert any(p.startswith("column:") for p in problems)


def test_results_dataframe_shape():
    from core.engine import ScanResult
    engine = InferenceEngine.__new__(InferenceEngine)  # no torch needed
    r = ScanResult(case_id="c1", prob_neg=0.4, prob_pos=0.6, prediction="Positive",
                   fold_probs={"f1": [0.4, 0.6]})
    df = engine.results_to_dataframe([r], {"c1": "Positive"})
    assert list(df.columns[:6]) == ["ID", "Label", "P(Negative)", "P(Positive)", "Prediction", "Ensemble_N"]
    assert df.loc[0, "Ensemble_N"] == 1
