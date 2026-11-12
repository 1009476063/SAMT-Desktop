"""Read the experiment CP.xlsx contract and match one case row.

This module does not translate fields into another study's feature names. The
column names and cell values are passed through to ``dataset.py`` unchanged.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .engine import CLINICAL_COLUMNS, PATHOLOGY_COLUMNS


REQUIRED_COLUMNS = ("ID",) + tuple(CLINICAL_COLUMNS) + tuple(PATHOLOGY_COLUMNS)


class ClinicalTableError(ValueError):
    """Raised when a workbook cannot be used as a SAMT CP table."""


@dataclass(frozen=True)
class TableMatch:
    """One unambiguous CP row and its source location."""
    row: dict[str, Any]
    source: str


def _clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _key(value: Any) -> str:
    text = _clean(value)
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.casefold()


def read_clinical_table(path: str | Path) -> pd.DataFrame:
    """Read Sheet1 (or the only sheet) with ID preserved as a string."""
    book = Path(path)
    try:
        sheets = pd.ExcelFile(book).sheet_names
    except Exception as exc:
        raise ClinicalTableError("unreadable: {}".format(exc)) from exc
    sheet = "Sheet1" if "Sheet1" in sheets else (sheets[0] if sheets else 0)
    try:
        df = pd.read_excel(book, sheet_name=sheet, dtype=object)
    except Exception as exc:
        raise ClinicalTableError("unreadable: {}".format(exc)) from exc
    if "ID" not in df.columns:
        raise ClinicalTableError("missing:ID")
    missing = [c for c in CLINICAL_COLUMNS + PATHOLOGY_COLUMNS
               if c not in df.columns]
    if missing:
        raise ClinicalTableError("missing-columns:{}".format(
            "; ".join(repr(c) for c in missing)))
    return df


def match_clinical_row(path: str | Path, case_id: str) -> TableMatch:
    """Return the unique row for ``case_id``, with no implicit fuzzy match."""
    df = read_clinical_table(path)
    query = _clean(case_id)
    if not query:
        df = df[df["ID"].map(_clean) != ""]
        if len(df) == 1:
            row = df.iloc[0].to_dict()
            return TableMatch(row, "{} / {} / row {}".format(
                Path(path).name, "Sheet1", int(df.index[0]) + 2))
        raise ClinicalTableError(
            "case-id-required:{}".format(len(df)))
    matches = df[df["ID"].map(_key) == _key(query)]
    if matches.empty:
        raise ClinicalTableError("no-row:{}".format(query))
    # Identical duplicate rows are harmless; differing duplicates are not.
    signatures = {
        tuple(_clean(row.get(column)) for column in REQUIRED_COLUMNS)
        for row in matches.to_dict("records")
    }
    if len(signatures) > 1:
        raise ClinicalTableError("ambiguous:{}".format(query))
    row = matches.iloc[0].to_dict()
    return TableMatch(row, "{} / {} / row {}".format(
        Path(path).name, "Sheet1", int(matches.index[0]) + 2))


def widget_value(column: str, value: Any) -> str:
    """Normalize a CP cell into a form field without changing its semantics."""
    text = _clean(value)
    if column in {"Age", "Tumor size MRI ",
                  "max diameter with lowest layer of ALN", "SLN-positive",
                  "total SLN", "Positive_Total_SLN_ratio"} and text.endswith(".0"):
        text = text[:-2]
    return text
