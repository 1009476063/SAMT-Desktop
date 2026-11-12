"""Lightweight experiment tree discovery for the UI.

The full engine keeps its own discovery logic for prediction; this catalog
has no pandas or NumPy import so the first workbench paint stays responsive.
"""
from __future__ import annotations

import glob
from dataclasses import dataclass
from pathlib import Path

from .experiment_contract import (
    CLINICAL_COLUMNS, PATHOLOGY_COLUMNS, REQUIRED_INPUT_GLOBS,
    experiment_tree_is_valid,
)


@dataclass(frozen=True)
class CatalogCase:
    case_id: str
    label_dir: str
    case_root: Path
    missing: tuple[str, ...]


def resolve_experiment_root(path: str | Path) -> tuple[Path, str | None]:
    """Resolve any selected folder to the nearest valid experiment root."""
    selected = Path(path).expanduser().resolve()
    if not selected.is_dir():
        return selected, None
    for parent in (selected, *selected.parents):
        if experiment_tree_is_valid(parent):
            return parent, selected.name if selected != parent else None
    return selected, None


def _find(case_root: Path, pattern: str) -> bool:
    return bool(glob.glob(str(case_root / pattern)))


def catalog_cases(data_root: str | Path,
                  only_case: str | None = None
                  ) -> tuple[list[CatalogCase], list[str]]:
    """List cases in the standard tree and report each missing model input."""
    root, selected_case = resolve_experiment_root(data_root)
    selected_case = only_case or selected_case
    if not experiment_tree_is_valid(root):
        missing = []
        if not (root / "MRMG").is_dir():
            missing.append("missing:MRMG")
        if not (root / "CP.xlsx").is_file():
            missing.append("missing:CP.xlsx")
        return [], missing
    cases: list[CatalogCase] = []
    problems: list[str] = []
    mrmg = root / "MRMG"
    for label in sorted(p.name for p in mrmg.iterdir() if p.is_dir()):
        for case_dir in sorted(p for p in (mrmg / label).iterdir()
                               if p.is_dir()):
            if selected_case and case_dir.name != selected_case:
                continue
            case_id = case_dir.name
            missing = []
            for name, pattern in REQUIRED_INPUT_GLOBS:
                if not _find(case_dir, pattern.format(id=case_id)):
                    missing.append(name)
            cases.append(CatalogCase(case_id, label, case_dir, tuple(missing)))
    if selected_case and not cases:
        problems.append("case-not-found:{}".format(selected_case))
    return cases, problems


def source_column_count() -> int:
    return len(CLINICAL_COLUMNS) + len(PATHOLOGY_COLUMNS)
