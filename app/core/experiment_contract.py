"""Static on-disk contract shared by the UI and inference engine.

This module deliberately has no heavy third-party imports: the consent gate
and first paint must not wait for pandas, NumPy, or PyTorch.
"""
from __future__ import annotations

from pathlib import Path


# Sheet1 column names of CP.xlsx (trailing spaces are significant).
CLINICAL_COLUMNS = [
    "Laterality ",
    "Multifocality（Tumor number）",
    "Location(nine)",
    "cT",
    "Calcification",
    "Breast density ",
    "Age",
    "Tumor size MRI ",
    "max diameter with lowest layer of ALN",
]
PATHOLOGY_COLUMNS = [
    "Histological type  (needle biopsy)",
    "Histological grade ",
    "ER",
    "PR",
    "HER2",
    "LVI",
    "Ki67",
    "SLN-positive",
    "total SLN",
    "Positive_Total_SLN_ratio",
]
SOURCE_COLUMNS = ("ID",) + tuple(CLINICAL_COLUMNS) + tuple(PATHOLOGY_COLUMNS)

# The original Dataset_img_clinical globs; the root name itself is arbitrary.
REQUIRED_INPUT_GLOBS = (
    ("DCE_N4", "{id}_DCE_N4.nii*"),
    ("DCE_decay1", "{id}_DCE_decay1.nii*"),
    ("MLO", "MG/*{id}_*MLO.nii*"),
    ("MLO_decay1", "MG/*{id}_*MLO_decay1.nii*"),
)


def experiment_tree_is_valid(root: Path) -> bool:
    """Whether a directory has the two invariants required by the Dataset."""
    root = Path(root)
    return (root / "MRMG").is_dir() and (root / "CP.xlsx").is_file()


def resolve_experiment_root(path: str | Path) -> tuple[Path, str | None]:
    """Resolve any selected folder to the nearest valid experiment root.

    Only a directory at ``MRMG/<Label>/<CaseID>`` is treated as a selected
    case. Ancillary folders such as ``MG``, ``MRMG``, or a label folder must
    not be mistaken for a case ID by the experiment's glob contract.
    """
    selected = Path(path).expanduser().resolve()
    if not selected.is_dir():
        return selected, None
    for parent in (selected, *selected.parents):
        if not experiment_tree_is_valid(parent):
            continue
        try:
            relative = selected.relative_to(parent / "MRMG")
        except ValueError:
            return parent, None
        parts = relative.parts
        if len(parts) >= 2:
            return parent, parts[1]
        return parent, None
    return selected, None


def experiment_tree_description() -> str:
    """Generic ASCII tree used as a fallback for the localized UI tree."""
    return (
        "StudyRoot/\n"
        "├── CP.xlsx\n"
        "└── MRMG/\n"
        "    └── <Label>/\n"
        "        └── <CaseID>/\n"
        "            ├── <CaseID>_DCE_N4.nii[.gz] (or <CaseID>_DCE.nii[.gz])\n"
        "            ├── <CaseID>_DCE_GTV.nii[.gz]\n"
        "            ├── <CaseID>_DCE_GTVnd1.nii[.gz]\n"
        "            └── MG/\n"
        "                ├── *<CaseID>*_MLO.nii[.gz]\n"
        "                ├── *<CaseID>*_MLO_GTV.nii[.gz]\n"
        "                └── *<CaseID>*_MLO_GTVnd1.nii[.gz]"
    )


def localized_problem(i18n, problem: str) -> str:
    """Translate one stable validation code while preserving its case/detail."""
    code, _, detail = problem.partition(":")
    keys = {
        "missing": "directory.error.missing",
        "unreadable": "directory.error.unreadable",
        "no-table-row": "directory.error.no_table_row",
        "case-not-found": "directory.error.case_not_found",
        "column": "directory.error.column",
        "DCE_N4": "inputs.dce_n4",
        "DCE_decay1": "inputs.dce_decay1",
        "MLO": "inputs.mlo",
        "MLO_decay1": "inputs.mlo_decay1",
        "source.dce": "source.dce",
        "source.dce_gtv": "source.dce_gtv",
        "source.mlo": "source.mlo",
        "source.mlo_gtv": "source.mlo_gtv",
        "preprocess.prepare": "preprocess.prepare",
        "prepare.incomplete": "prepare.incomplete",
        "shape": "preprocess.error.shape",
    }
    key = keys.get(code)
    if not key:
        return problem
    if code == "prepare.incomplete":
        case_id, _, missing = detail.partition(":")
        source_key = missing if missing.startswith("source.") \
            else "source." + missing
        return i18n.tr(key, detail=case_id,
                       names=i18n.tr(source_key, fallback=missing))
    if detail and key == "preprocess.error.shape":
        return i18n.tr(key, names=detail.replace(":", " / "))
    return i18n.tr(key, detail=detail) if detail else i18n.tr(key)
