import sys
from pathlib import Path

import pandas as pd

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from core.engine import (  # noqa: E402
    CLINICAL_COLUMNS, PATHOLOGY_COLUMNS, discover_cases,
    resolve_experiment_root,
)


def test_selected_case_directory_resolves_to_experiment_root(tmp_path):
    root = tmp_path / "NSLN"
    case = root / "MRMG" / "Positive" / "case2"
    (case / "MG").mkdir(parents=True)
    for name in ("case2_DCE_N4.nii.gz", "case2_DCE_decay1.nii.gz"):
        (case / name).write_bytes(b"test")
    for name in ("case2_MG_MLO.nii.gz", "case2_MLO_decay1.nii.gz"):
        (case / "MG" / name).write_bytes(b"test")
    row = {column: "0" for column in
           CLINICAL_COLUMNS + PATHOLOGY_COLUMNS}
    row["ID"] = "case2"
    pd.DataFrame([row]).to_excel(root / "CP.xlsx",
                                 sheet_name="Sheet1", index=False)
    assert resolve_experiment_root(case) == (root.resolve(), "case2")
    cases, problems = discover_cases(case)
    assert problems == []
    assert [item.case_id for item in cases] == ["case2"]
    assert cases[0].label_dir == "Positive"
