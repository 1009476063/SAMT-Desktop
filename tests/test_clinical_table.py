import sys
from pathlib import Path

import pandas as pd

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from core.clinical_table import (  # noqa: E402
    ClinicalTableError, match_clinical_row, read_clinical_table, widget_value,
)
from core.engine import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS  # noqa: E402


def _workbook(path: Path, rows: list[dict]) -> Path:
    columns = ["ID"] + CLINICAL_COLUMNS + PATHOLOGY_COLUMNS
    data = [{column: "0" for column in columns} for _ in rows]
    for table_row, values in zip(data, rows):
        table_row.update(values)
    pd.DataFrame(data).to_excel(path, sheet_name="Sheet1", index=False)
    return path


def test_unique_case_match_preserves_exact_columns(tmp_path):
    path = _workbook(tmp_path / "CP.xlsx", [
        {"ID": "case1", "Age": 49, "Ki67": ">=20%"},
        {"ID": "case2", "Age": 33, "Ki67": "<20%"},
    ])
    table = read_clinical_table(path)
    assert list(table["ID"]) == ["case1", "case2"]
    match = match_clinical_row(path, "case2")
    assert match.row["Age"] == 33
    assert match.row["Ki67"] == "<20%"
    assert widget_value("Age", match.row["Age"]) == "33"
    assert widget_value("Positive_Total_SLN_ratio", 1.0) == "1"
    assert "row 3" in match.source


def test_ambiguous_or_absent_match_is_rejected(tmp_path):
    path = _workbook(tmp_path / "CP.xlsx", [
        {"ID": "case1", "Age": 49}, {"ID": "case1", "Age": 50},
    ])
    try:
        match_clinical_row(path, "case1")
    except ClinicalTableError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("ambiguous duplicate rows must be rejected")
    try:
        match_clinical_row(path, "missing")
    except ClinicalTableError as exc:
        assert "no-row" in str(exc)
    else:
        raise AssertionError("unknown case ID must be rejected")


def test_single_row_workbook_does_not_require_typed_case_id(tmp_path):
    path = _workbook(tmp_path / "CP.xlsx", [{"ID": "patient-7"}])
    match = match_clinical_row(path, "")
    assert match.row["ID"] == "patient-7"
