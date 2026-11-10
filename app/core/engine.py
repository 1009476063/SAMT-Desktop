"""Inference engine: bridges the GUI to the original SAMT research code.

The engine never re-implements preprocessing or feature encoding. It stages
cases on disk in the exact layout expected by ``samt_core.dataset`` and reuses
its Dataset classes through generated single-case split pickles.
"""
from __future__ import annotations

import glob
import os
import pickle
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np
import pandas as pd

from .samt_core import _ensure_importable

_ensure_importable()

from .samt_core.dataset import Dataset_img_clinical


TASK = "pathology_pretrain"
TRAIN_SUBDIR = "trained_models"
DIRNAME_TEMPLATE = "bs4_epoch100_seed42_{date}_drop0"

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


@dataclass
class PatientCase:
    case_id: str
    label_dir: str  # "Positive" / "Negative" as on disk; drives path layout only
    case_root: Path  # directory containing the NIfTI files (+ MG subdir)
    table_row: dict = field(default_factory=dict)  # CP.xlsx row for this ID


@dataclass
class ScanResult:
    case_id: str
    prob_neg: float
    prob_pos: float
    prediction: str  # "Negative" / "Positive"
    fold_probs: dict[str, Optional[list[float]]]


def _core_dir() -> Path:
    return Path(__file__).resolve().parent / "samt_core"


def find_case_nifti(case_root: Path, pattern: str) -> Optional[Path]:
    hits = sorted(glob.glob(str(case_root / pattern)))
    return Path(hits[0]) if hits else None


def validate_case(case: PatientCase) -> list[str]:
    """Return human-readable problems; empty list means the case is runnable."""
    problems = []
    if find_case_nifti(case.case_root, "{}_DCE_N4.nii*".format(case.case_id)) is None:
        problems.append("DCE_N4")
    if find_case_nifti(case.case_root, "{}_DCE_decay1.nii*".format(case.case_id)) is None:
        problems.append("DCE_decay1")
    if find_case_nifti(case.case_root / "MG", "*{}_*MLO.nii*".format(case.case_id)) is None:
        problems.append("MLO")
    if find_case_nifti(case.case_root / "MG", "*{}_*MLO_decay1.nii*".format(case.case_id)) is None:
        problems.append("MLO_decay1")
    for col in CLINICAL_COLUMNS + PATHOLOGY_COLUMNS:
        if col not in case.table_row:
            problems.append("column:" + col.strip())
    return problems


def discover_cases(data_root: Path) -> tuple[list[PatientCase], list[str]]:
    """Scan an experiment-style tree: MRMG/<Label>/<ID> + CP.xlsx at root."""
    problems: list[str] = []
    cases: list[PatientCase] = []
    mrmg = data_root / "MRMG"
    cp = data_root / "CP.xlsx"
    if not mrmg.is_dir():
        problems.append("missing:MRMG")
    if not cp.is_file():
        problems.append("missing:CP.xlsx")
    if problems:
        return cases, problems
    try:
        df = pd.read_excel(cp, sheet_name="Sheet1", dtype={"ID": str})
        df["ID"] = df["ID"].astype(str)
    except Exception as exc:  # pragma: no cover - surfaced to the UI
        return cases, ["unreadable:CP.xlsx:{}".format(exc)]
    for label in sorted(p.name for p in mrmg.iterdir() if p.is_dir()):
        for case_dir in sorted(p for p in (mrmg / label).iterdir() if p.is_dir()):
            row_matches = df.loc[df["ID"] == case_dir.name]
            if row_matches.empty:
                problems.append("no-table-row:{}".format(case_dir.name))
                continue
            cases.append(PatientCase(
                case_id=case_dir.name,
                label_dir=label,
                case_root=case_dir,
                table_row=row_matches.iloc[0].to_dict(),
            ))
    return cases, problems


class InferenceEngine:
    """Loads the 10 fold checkpoints once and scans staged cases."""

    def __init__(self, models_dir: Path, device: Optional[str] = None):
        import torch
        self._torch_mod = torch
        if device is None:
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = torch.device(device)
        self.models_dir = Path(models_dir)
        self._ckpt_paths = self._discover_checkpoints()
        self._nets: list = []
        self._scratch = Path(tempfile.mkdtemp(prefix="samt_desktop_"))

    # ---- checkpoints -------------------------------------------------
    def _discover_checkpoints(self) -> list[Path]:
        # Ship layout: models_dir/fold{N}_{best_AUC_val,best_ACC_val}.pth
        hits = sorted(self.models_dir.glob("pathology_pretrain_fold*_*.pth"))
        if hits:
            return hits
        # Fallback: original training tree layout.
        legacy = sorted(self.models_dir.glob("**/*.pth"))
        return legacy

    @property
    def checkpoint_count(self) -> int:
        return len(self._ckpt_paths)

    def _build_networks(self):
        if self._nets:
            return self._nets
        torch = self.torch
        from .samt_core.Multimodal_Fusion_Network import (
            MFNet_img_pathology_transcat_l3m_orgTransformer_1,
        )
        for ckpt in self._ckpt_paths:
            net = MFNet_img_pathology_transcat_l3m_orgTransformer_1(
                n_classes=2, no_cuda=False, drop=0)
            state = torch.load(str(ckpt), map_location="cpu")
            net.load_state_dict(state)
            net.to(self.device)
            net.eval()
            self._nets.append((ckpt.name, net))
        return self._nets

    # ---- staging -----------------------------------------------------
    def stage_case(self, case: PatientCase, table_df: Optional[pd.DataFrame] = None) -> Path:
        """Materialise a case into scratch in the dataset.py layout."""
        case_scratch = self._scratch / case.case_id
        case_scratch.mkdir(parents=True, exist_ok=True)
        # dataset.py joins data_dir/MRMG/<label>/<ID>/...; MRMG level is required.
        target = case_scratch / "MRMG" / case.label_dir / case.case_id
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        # MG is symlinked separately below; copy images first.
        shutil.copytree(case.case_root, target,
                        ignore=shutil.ignore_patterns("MG"))
        mg_src = case.case_root / "MG"
        if mg_src.is_dir():
            shutil.copytree(mg_src, target / "MG")
        # Write CP.xlsx with just this case (dataset.py reads Sheet1).
        if table_df is None:
            table_df = pd.DataFrame([case.table_row])
        table_df.to_excel(case_scratch / "CP.xlsx", sheet_name="Sheet1", index=False)
        return case_scratch

    def _build_loader(self, staged_root: Path, case: PatientCase):
        from torch.utils.data import DataLoader
        split_path = staged_root / "single.pkl"
        split = {"test": [{"ID": case.case_id, "label": case.label_dir}]}
        with open(split_path, "wb") as fh:
            pickle.dump(split, fh)
        ds = Dataset_img_clinical(str(staged_root), str(split_path),
                                  data_set="test", augment=False)
        return DataLoader(ds, batch_size=1, shuffle=False, num_workers=0)

    # ---- inference ---------------------------------------------------
    @property
    def torch(self):
        return self._torch_mod

    def infer_case(self, case: PatientCase, progress: Optional[Callable[[str], None]] = None) -> ScanResult:
        torch = self.torch
        nets = self._build_networks()
        staged = self.stage_case(case)
        if progress:
            progress("preprocess")
        loader = self._build_loader(staged, case)
        batch = next(iter(loader))
        # batch = (ID, img_MR_DCE, img_MG_MLO, clinical, pathology, label)
        net_args = [t.to(self.device).float() for t in batch[1:5]]
        fold_probs: dict[str, Optional[list[float]]] = {}
        prob_sum = np.zeros(2, dtype=np.float64)
        ok = 0
        for name, net in nets:
            if progress:
                progress("fold:{}".format(name))
            with torch.no_grad():
                logits = net(*net_args)[-1]
                prob = torch.softmax(logits, dim=1)[0].cpu().numpy()
            fold_probs[name] = [float(prob[0]), float(prob[1])]
            prob_sum += prob
            ok += 1
        if ok == 0:
            raise RuntimeError("no checkpoint produced a prediction")
        mean_prob = prob_sum / ok
        pred = "Positive" if int(np.argmax(mean_prob)) == 1 else "Negative"
        return ScanResult(case_id=case.case_id,
                          prob_neg=float(mean_prob[0]),
                          prob_pos=float(mean_prob[1]),
                          prediction=pred,
                          fold_probs=fold_probs)

    def infer_batch(self, cases: Iterable[PatientCase],
                    progress: Optional[Callable[[str, int, int], None]] = None) -> list[ScanResult]:
        cases = list(cases)
        results = []
        for i, case in enumerate(cases, 1):
            result = self.infer_case(case, progress=None)
            results.append(result)
            if progress:
                progress(case.case_id, i, len(cases))
        return results

    def results_to_dataframe(self, results: list[ScanResult], labels: Optional[dict[str, str]] = None) -> pd.DataFrame:
        rows = []
        for r in results:
            row = {
                "ID": r.case_id,
                "Label": (labels or {}).get(r.case_id, ""),
                "P(Negative)": round(r.prob_neg, 6),
                "P(Positive)": round(r.prob_pos, 6),
                "Prediction": r.prediction,
                "Ensemble_N": sum(v is not None for v in r.fold_probs.values()),
            }
            for name, probs in r.fold_probs.items():
                if probs is not None:
                    row["{}_P(neg)".format(name)] = round(probs[0], 6)
                    row["{}_P(pos)".format(name)] = round(probs[1], 6)
                else:
                    row["{}_P(neg)".format(name)] = ""
                    row["{}_P(pos)".format(name)] = ""
            rows.append(row)
        return pd.DataFrame(rows)

    def cleanup(self):
        if self._scratch.exists():
            shutil.rmtree(self._scratch, ignore_errors=True)
