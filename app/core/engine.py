"""Inference engine: bridges the GUI to the original SAMT research code.

The engine never re-implements preprocessing or feature encoding. It stages
cases on disk in the exact layout expected by ``samt_core.dataset`` and reuses
its Dataset classes through generated single-case split pickles.
"""
from __future__ import annotations

import ctypes
import glob
import hashlib
import json
import os
import pickle
import shutil
import sys
import tempfile
import threading
import time
import weakref
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

import numpy as np
import pandas as pd

from .samt_core import _ensure_importable
from .experiment_contract import (
    CLINICAL_COLUMNS, PATHOLOGY_COLUMNS, REQUIRED_INPUT_GLOBS,
    resolve_experiment_root,
)
from .preprocessing import prepared_clinical_table

_ensure_importable()


TASK = "pathology_pretrain"
TRAIN_SUBDIR = "trained_models"
DIRNAME_TEMPLATE = "bs4_epoch100_seed42_{date}_drop0"

@dataclass
class PatientCase:
    case_id: str
    label_dir: str  # "Positive" / "Negative" as on disk; drives path layout only
    case_root: Path  # directory containing the NIfTI files (+ MG subdir)
    table_row: dict = field(default_factory=dict)  # CP.xlsx row for this ID
    clinical_table: Optional[Path] = None  # staged workbook with derived cells
    dce_n4: Optional[Path] = None
    dce_decay: Optional[Path] = None
    mlo: Optional[Path] = None
    mlo_decay: Optional[Path] = None


@dataclass
class ScanResult:
    case_id: str
    prob_neg: float
    prob_pos: float
    prediction: str  # "Negative" / "Positive"
    fold_probs: dict[str, Optional[list[float]]]


@dataclass
class EngineStatus:
    checkpoint_count: int
    requested_device: str
    active_device: str
    load_seconds: float = 0.0
    backend_note: str = ""


def _core_dir() -> Path:
    return Path(__file__).resolve().parent / "samt_core"


def find_case_nifti(case_root: Path, pattern: str) -> Optional[Path]:
    hits = sorted(glob.glob(str(case_root / pattern)))
    return Path(hits[0]) if hits else None


def checkpoint_fingerprint(paths: list[Path]) -> str:
    """Stable identity for the shipped ensemble, without reading 1.7 GiB."""
    digest = hashlib.sha256()
    for path in paths:
        stat = path.stat()
        digest.update(path.name.encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return digest.hexdigest()[:12]


def load_stored_checkpoint(path: Path, name: str) -> dict:
    """Reconstruct one checkpoint state dict from a shared-tensor store."""
    import torch
    with zipfile.ZipFile(Path(path)) as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names or "tensors.bin" not in names:
            raise ValueError("invalid checkpoint store: {}".format(path))
        manifest_bytes = archive.read("manifest.json")
        tensor_bytes = archive.read("tensors.bin")
        manifest = json.loads(manifest_bytes)
        if hashlib.sha256(tensor_bytes).hexdigest() != manifest["tensor_sha256"]:
            raise ValueError("checkpoint digest mismatch: {}".format(path))
        if name not in manifest["state"]:
            raise ValueError("checkpoint not in store: {}".format(name))
        tensors = []
        offset = 0
        for item in manifest["blobs"]:
            length = int(item["size"])
            raw = tensor_bytes[offset:offset + length]
            dtype = getattr(torch, item["dtype"])
            storage = torch.empty(0, dtype=dtype).untyped_storage()
            storage.resize_(length)
            ctypes.memmove(storage.data_ptr(), raw, length)
            tensor = torch.empty(0, dtype=dtype).set_(
                storage, 0, item["shape"], None).clone()
            tensors.append(tensor)
            offset += length
        return {key: tensors[int(index)] for key, index in
                manifest["state"][name].items()}


def load_checkpoint_state(path: Path) -> object:
    """Load one raw torch checkpoint; stores require an explicit fold name."""
    import torch
    path = Path(path)
    if zipfile.is_zipfile(path):
        raise ValueError("use load_stored_checkpoint for ensemble stores")
    return torch.load(str(path), map_location="cpu")


def build_checkpoint_store(paths: list[Path], target: Path) -> dict:
    """Store each unique tensor's raw bytes once across all ten checkpoints."""
    import torch
    if len(paths) != 10:
        raise ValueError("expected 10 fold checkpoints")
    states = [torch.load(str(path), map_location="cpu") for path in paths]
    blob_index: dict[tuple[str, bytes], int] = {}
    blobs: list[bytes] = []
    blob_meta: list[dict] = []
    checkpoint_maps: dict[str, dict[str, int]] = {}
    for path, state in zip(paths, states):
        key_map: dict[str, int] = {}
        for key, tensor in state.items():
            if not torch.is_tensor(tensor):
                raise ValueError("non-tensor state in {}".format(path.name))
            storage = tensor.detach().cpu().contiguous().untyped_storage()
            raw = bytes((ctypes.c_ubyte * storage.nbytes()).from_address(
                storage.data_ptr()))
            identity = (str(tensor.dtype).replace("torch.", ""), raw)
            index = blob_index.get(identity)
            if index is None:
                index = len(blobs)
                blob_index[identity] = index
                blobs.append(raw)
                blob_meta.append({"dtype": identity[0],
                                  "shape": list(tensor.shape),
                                  "size": len(raw)})
            key_map[key] = index
        checkpoint_maps[path.name] = key_map
    payload = b"".join(blobs)
    manifest = {
        "format": "samt-lossless-checkpoint-store-v1",
        "tensor_sha256": hashlib.sha256(payload).hexdigest(),
        "blobs": blob_meta,
        "state": checkpoint_maps,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps(
            manifest, ensure_ascii=False, separators=(",", ":")))
        archive.writestr("tensors.bin", payload)
    return {
        "checkpoints": len(paths),
        "raw_tensor_bytes": sum(t.numel() * t.element_size()
                                for state in states for t in state.values()),
        "unique_tensor_bytes": len(payload),
        "unique_tensors": len(blobs),
    }


def validate_case(case: PatientCase) -> list[str]:
    """Return human-readable problems; empty list means the case is runnable."""
    problems = []
    explicit = {
        "DCE_N4": getattr(case, "dce_n4", None),
        "DCE_decay1": getattr(case, "dce_decay", None),
        "MLO": getattr(case, "mlo", None),
        "MLO_decay1": getattr(case, "mlo_decay", None),
    }
    from .preprocessing import derivable_products

    derivable = set(derivable_products(case.case_root, case.case_id))
    for name, pattern in REQUIRED_INPUT_GLOBS:
        path = explicit.get(name)
        if path is not None:
            if not Path(path).is_file():
                problems.append(name)
            continue
        if name in derivable:
            continue
        search_root = case.case_root / "MG" \
            if pattern.startswith("MG/") else case.case_root
        relative = pattern[3:] if pattern.startswith("MG/") else pattern
        if find_case_nifti(search_root,
                           relative.format(id=case.case_id)) is None:
            problems.append(name)
    for col in CLINICAL_COLUMNS + PATHOLOGY_COLUMNS:
        if col not in case.table_row:
            problems.append("column:" + col.strip())
    return problems


def discover_cases(data_root: Path,
                   only_case: str | None = None) -> tuple[list[PatientCase], list[str]]:
    """Scan an experiment tree; a selected case dir limits the scan to it."""
    problems: list[str] = []
    cases: list[PatientCase] = []
    root, selected_case = resolve_experiment_root(data_root)
    only_case = only_case or selected_case
    mrmg = root / "MRMG"
    cp = prepared_clinical_table(root)
    if not mrmg.is_dir():
        problems.append("missing:MRMG")
    if not (root / "CP.xlsx").is_file():
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
            if only_case and case_dir.name != only_case:
                continue
            row_matches = df.loc[df["ID"] == case_dir.name]
            if row_matches.empty:
                problems.append("no-table-row:{}".format(case_dir.name))
                continue
            cases.append(PatientCase(
                case_id=case_dir.name,
                label_dir=label,
                case_root=case_dir,
                table_row=row_matches.iloc[0].to_dict(),
                dce_n4=find_case_nifti(case_dir, "{}_DCE_N4.nii*".format(
                    case_dir.name)),
                dce_decay=find_case_nifti(
                    case_dir, "{}_DCE_decay1.nii*".format(case_dir.name)),
                mlo=None,
                mlo_decay=find_case_nifti(
                    case_dir / "MG",
                    "*{}_*MLO_decay1.nii*".format(case_dir.name)),
            ))
    if only_case and not cases:
        problems.append("case-not-found:{}".format(only_case))
    return cases, problems


class InferenceEngine:
    """Runs the 10 fold checkpoints through one shared network.

    All checkpoints use the same architecture. Loading each state_dict into a
    single eval-mode model is mathematically identical to retaining ten model
    instances, while avoiding nine extra backbone constructions. The retained
    state dicts still account for most memory; low-memory mode rereads each
    checkpoint at inference time instead.
    """

    def __init__(self, models_dir: Path, device: Optional[str] = None,
                 on_status: Optional[Callable[[str], None]] = None,
                 retain_checkpoints: bool = True):
        import torch
        self._torch_mod = torch
        requested = device or self.default_device(torch)
        if requested not in self.available_devices(torch):
            requested = self.default_device(torch)
        self.requested_device = requested
        self.device = torch.device(requested)
        self._on_status = on_status
        self.retain_checkpoints = retain_checkpoints
        self.models_dir = Path(models_dir)
        self._ckpt_paths = self._discover_checkpoints()
        self.fingerprint = checkpoint_fingerprint(self._ckpt_paths)
        self._checkpoint_states: dict[str, object] = {}
        self._shared_net = None
        self._nets_lock = threading.Lock()
        self._load_seconds = 0.0
        self._scratch = Path(tempfile.mkdtemp(prefix="samt_desktop_"))
        weakref.finalize(self, shutil.rmtree, str(self._scratch), True)
        self._pretrain_path = _core_dir() / "Networks" / "resnet_18_23dataset.pth"
        self._pretrain_state = None
        self._pretrain_lock = threading.Lock()
        self._backend_probe_error = ""

    @staticmethod
    def default_device(torch) -> str:
        """CPU is the deterministic reference; accelerators are opt-in.

        Backend kernels can change floating-point reduction order by a few ULPs.
        Keeping CPU as default preserves the numerical behaviour of the
        published experiment while CUDA/MPS remain available explicitly.
        """
        return "cpu"

    @staticmethod
    def available_devices(torch) -> list[str]:
        devices = ["cpu"]
        if torch.cuda.is_available():
            devices.append("cuda")
        mps = getattr(torch.backends, "mps", None)
        if mps is not None and mps.is_available():
            devices.append("mps")
        return devices

    # ---- checkpoints -------------------------------------------------
    def _discover_checkpoints(self) -> list[Path]:
        # Prefer the verified, byte-lossless ensemble store when present.
        store = self.models_dir / "samt-checkpoints.zip"
        if store.is_file():
            return [store]
        # Ship layout: models_dir/fold{N}_{best_AUC_val,best_ACC_val}.pth
        hits = sorted(self.models_dir.glob("pathology_pretrain_fold*_*.pth"))
        if hits:
            return hits
        # Fallback: original training tree layout. Exclude backbone weights.
        legacy = sorted(
            path for path in self.models_dir.glob("**/*.pth")
            if path.name != "resnet_18_23dataset.pth"
        )
        return legacy

    @property
    def checkpoint_count(self) -> int:
        if len(self._ckpt_paths) == 1 and \
                self._ckpt_paths[0].name == "samt-checkpoints.zip":
            with zipfile.ZipFile(self._ckpt_paths[0]) as archive:
                return len(json.loads(archive.read("manifest.json"))["state"])
        return len(self._ckpt_paths)

    def _build_networks(self):
        with self._nets_lock:
            if self._shared_net is not None and self._checkpoint_states:
                return self._checkpoint_states
            torch = self.torch
            from .samt_core.Multimodal_Fusion_Network import (
                MFNet_img_pathology_transcat_l3m_orgTransformer_1,
            )
            from .samt_core import ResNet_3D
            # The vendored backbone reads this checkpoint ten times. Patch the
            # loader only for the tightly scoped construction loop; the loaded
            # tensors and state_dict contents stay identical.
            cached_pretrain = self._pretrain_state
            real_load = torch.load
            pretrain_path = str(self._pretrain_path)
            pretrain_path_variants = {
                pretrain_path,
                str(self._pretrain_path.resolve()),
            }

            def cached_load(path, *args, **kwargs):
                if (str(path) in pretrain_path_variants and
                        self._pretrain_state is not None):
                    return cached_pretrain
                return real_load(path, *args, **kwargs)

            with self._pretrain_lock:
                if cached_pretrain is None:
                    cached_pretrain = real_load(pretrain_path, map_location="cpu")
                    self._pretrain_state = cached_pretrain
                ResNet_3D.torch.load = cached_load
            try:
                shared_net, states = self._construct_networks(torch,
                    MFNet_img_pathology_transcat_l3m_orgTransformer_1,
                    load_checkpoint_state)
            finally:
                ResNet_3D.torch.load = real_load
            self._shared_net = shared_net
            self._checkpoint_states = states
            return self._checkpoint_states

    def _construct_networks(self, torch, net_class, checkpoint_loader):
        net = net_class(n_classes=2, no_cuda=False, drop=0)
        net.to(self.device)
        net.eval()
        states: dict[str, object] = {}
        if len(self._ckpt_paths) == 1 and \
                self._ckpt_paths[0].name == "samt-checkpoints.zip":
            with zipfile.ZipFile(self._ckpt_paths[0]) as archive:
                names = list(json.loads(
                    archive.read("manifest.json"))["state"])
            for index, name in enumerate(names, 1):
                if self.retain_checkpoints:
                    states[name] = self._load_store_checkpoint(name)
                else:
                    # Keep all ten ordered fold identities; _predict_states
                    # rereads each state dict when low-memory mode is active.
                    states[name] = name
                if self._on_status:
                    self._on_status("checkpoint:{}:{}".format(index, len(names)))
        else:
            for index, ckpt in enumerate(self._ckpt_paths, 1):
                if self.retain_checkpoints:
                    state = checkpoint_loader(ckpt)
                    states[ckpt.name] = state
                    del state
                else:
                    states[ckpt.name] = ckpt
                if self._on_status:
                    self._on_status("checkpoint:{}:{}".format(
                        index, len(self._ckpt_paths)))
        return net, states

    def _checkpoints(self) -> tuple[object, dict[str, object]]:
        states = self._build_networks()
        if self._shared_net is None:
            raise RuntimeError("model ensemble is not available")
        return self._shared_net, states

    def _predict_states(self, net, states, net_args,
                        progress: Optional[Callable[[str], None]] = None):
        torch = self.torch
        fold_probs: dict[str, Optional[list[float]]] = {}
        prob_sum = np.zeros(2, dtype=np.float64)
        for index, (name, state) in enumerate(states.items(), 1):
            if not self.retain_checkpoints:
                if isinstance(state, Path):
                    state = load_checkpoint_state(state)
                elif isinstance(state, str) and name == state:
                    state = self._load_store_checkpoint(name)
            net.load_state_dict(state)
            if progress:
                progress("fold:{}".format(name))
            elif self._on_status:
                self._on_status("fold:{}:{}".format(index, len(states)))
            with torch.no_grad():
                logits = net(*net_args)[-1]
                prob = torch.softmax(logits, dim=1)[0].cpu().numpy()
            fold_probs[name] = [float(prob[0]), float(prob[1])]
            prob_sum += prob
            if not self.retain_checkpoints:
                del state
        return fold_probs, prob_sum / max(len(states), 1)

    def _load_store_checkpoint(self, name: str):
        return load_stored_checkpoint(self._ckpt_paths[0], name)

    def _probe_backend(self, net) -> bool:
        """Exercise the vendored 3D path before committing to an accelerator."""
        if self.device.type == "cpu":
            return True
        torch = self.torch
        probe = [
            torch.zeros((1, 2, 16, 32, 32), device=self.device),
            torch.zeros((1, 2, 64, 64), device=self.device),
            torch.zeros((1, 32), device=self.device),
            torch.zeros((1, 23), device=self.device),
        ]
        try:
            with torch.no_grad():
                net(*probe)
            return True
        except Exception as exc:
            self._backend_probe_error = str(exc)
            return False
        finally:
            del probe

    # ---- staging -----------------------------------------------------
    @staticmethod
    def _link_or_copy(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except OSError:
            shutil.copy2(source, target)

    def _stage_image(self, target: Path, case: PatientCase, kind: str) -> None:
        patterns = {
            "dce": (REQUIRED_INPUT_GLOBS[0][1], "{}_DCE_N4.nii.gz", Path(".")),
            "dce_decay": (REQUIRED_INPUT_GLOBS[1][1],
                          "{}_DCE_decay1.nii.gz", Path(".")),
            "mlo": (REQUIRED_INPUT_GLOBS[2][1][3:],
                    "{}_MG_MLO.nii.gz", Path("MG")),
            "mlo_decay": (REQUIRED_INPUT_GLOBS[3][1][3:],
                          "{}_MLO_decay1.nii.gz", Path("MG")),
        }
        pattern, fallback_name, subdir = patterns[kind]
        explicit = {
            "dce": getattr(case, "dce_n4", None),
            "dce_decay": getattr(case, "dce_decay", None),
            "mlo": getattr(case, "mlo", None),
            "mlo_decay": getattr(case, "mlo_decay", None),
        }.get(kind)
        source = Path(explicit) if explicit is not None else None
        if source is None and kind == "mlo":
            from .preprocessing import find_mlo_image

            source = find_mlo_image(case.case_root, case.case_id)
        if source is None and kind == "mlo_decay":
            source = find_case_nifti(
                case.case_root / "MG",
                "*{}_*MLO_decay1.nii*".format(case.case_id))
        if source is None:
            candidates = sorted((case.case_root / subdir).glob(
                pattern.format(id=case.case_id)))
            if kind == "mlo":
                from .preprocessing import find_mlo_image  # noqa: F401

                candidates = [
                    path for path in candidates
                    if "_GTV" not in path.name and
                    "_decay" not in path.name
                ]
            source = candidates[0] if candidates else None
        if source is None:
            raise FileNotFoundError("{}: {}".format(kind, case.case_id))
        self._link_or_copy(source, target / subdir /
                           fallback_name.format(case.case_id))

    def stage_cases(self, cases: list[PatientCase],
                    table_df: Optional[pd.DataFrame] = None) -> Path:
        """Materialise one or more cases in the dataset.py directory layout.

        Only the four model inputs are staged; unrelated contours and raw
        volumes are not copied. A single CP.xlsx is written for the batch so
        repeated cases do not pay for redundant spreadsheet writes.
        """
        batch_root = self._scratch / "batch"
        if batch_root.exists():
            shutil.rmtree(batch_root)
        batch_root.mkdir(parents=True)
        for case in cases:
            target = batch_root / "MRMG" / case.label_dir / case.case_id
            target.mkdir(parents=True)
            for kind in ("dce", "dce_decay", "mlo", "mlo_decay"):
                self._stage_image(target, case, kind)
        staged_workbooks = {
            Path(getattr(case, "clinical_table", ""))
            for case in cases
            if getattr(case, "clinical_table", None)
        }
        if table_df is None and len(staged_workbooks) == 1:
            table_df = pd.read_excel(
                staged_workbooks.pop(), sheet_name="Sheet1", dtype={"ID": str})
        elif table_df is None:
            rows = []
            for case in cases:
                row = dict(case.table_row)
                row["ID"] = case.case_id
                rows.append(row)
            table_df = pd.DataFrame(rows)
        else:
            table_df = table_df.copy()
        if "ID" in table_df.columns:
            table_df["ID"] = table_df["ID"].astype(str)
        table_df.to_excel(batch_root / "CP.xlsx", sheet_name="Sheet1", index=False)
        return batch_root

    def stage_case(self, case: PatientCase,
                   table_df: Optional[pd.DataFrame] = None) -> Path:
        return self.stage_cases([case], table_df)

    def _build_loader(self, staged_root: Path, case: PatientCase):
        from torch.utils.data import DataLoader
        from .samt_core.dataset import Dataset_img_clinical
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
        net, states = self._checkpoints()
        staged = self.stage_case(case)
        if progress:
            progress("preprocess:{}".format(case.case_id))
        loader = self._build_loader(staged, case)
        batch = next(iter(loader))
        generated = getattr(loader.dataset, "df", None)
        if generated is not None and "ID" in generated.columns:
            case.table_row = generated.iloc[0].to_dict()
        # batch = (ID, img_MR_DCE, img_MG_MLO, clinical, pathology, label)
        net_args = [t.to(self.device).float() for t in batch[1:5]]
        fold_probs, mean_prob = self._predict_states(
            net, states, net_args, progress)
        del net_args, loader, batch
        if not states:
            raise RuntimeError("no checkpoint produced a prediction")
        pred = "Positive" if int(np.argmax(mean_prob)) == 1 else "Negative"
        return ScanResult(case_id=case.case_id,
                          prob_neg=float(mean_prob[0]),
                          prob_pos=float(mean_prob[1]),
                          prediction=pred,
                          fold_probs=fold_probs)

    def warm_up(self) -> None:
        """Prepare the shared network ensemble before the first case is queued."""
        started = time.perf_counter()
        self._build_networks()
        net = self._shared_net
        if net is not None and not self._probe_backend(net):
            if self.requested_device == "cpu":
                raise RuntimeError("CPU backend probe failed")
            # MPS 2.3 lacks max_pool3d; CUDA drivers can have similar gaps.
            # Rebuilding on CPU keeps the exact research result available.
            states = dict(self._checkpoint_states)
            self._shared_net = None
            self._checkpoint_states = {}
            self.device = self.torch.device("cpu")
            from .samt_core.Multimodal_Fusion_Network import (
                MFNet_img_pathology_transcat_l3m_orgTransformer_1,
            )
            net = MFNet_img_pathology_transcat_l3m_orgTransformer_1(
                n_classes=2, no_cuda=False, drop=0)
            net.eval()
            self._shared_net = net
            self._checkpoint_states = states
            if self._on_status:
                self._on_status("fallback:cpu")
        self._load_seconds = time.perf_counter() - started

    def status(self) -> EngineStatus:
        torch = self.torch
        note = ""
        if self.requested_device != "cpu":
            note = "backend warning: probabilities may differ slightly"
        if str(self.device) == "cpu" and self.requested_device != "cpu":
            note = "backend fallback: CPU reference"
        return EngineStatus(
            checkpoint_count=self.checkpoint_count,
            requested_device=self.requested_device,
            active_device=str(self.device),
            load_seconds=self._load_seconds,
            backend_note=note,
        )

    @property
    def backend_probe_error(self) -> str:
        return self._backend_probe_error

    def infer_batch(self, cases: Iterable[PatientCase],
                    progress: Optional[Callable[[str, int, int], None]] = None) -> list[ScanResult]:
        cases = list(cases)
        return self.infer_staged_batch(cases, progress=progress)

    def infer_staged_batch(self, cases: list[PatientCase],
                           progress: Optional[Callable[[str, int, int], None]] = None) -> list[ScanResult]:
        """Reuse one CP.xlsx and the loaded ensemble across a batch."""
        net, states = self._checkpoints()
        staged_root = self.stage_cases(cases)
        from .samt_core.dataset import Dataset_img_clinical
        from torch.utils.data import DataLoader
        split = {"test": [{"ID": c.case_id, "label": c.label_dir} for c in cases]}
        split_path = staged_root / "batch.pkl"
        with open(split_path, "wb") as fh:
            pickle.dump(split, fh)
        dataset = Dataset_img_clinical(
            str(staged_root), str(split_path), data_set="test", augment=False)
        loader = DataLoader(dataset, batch_size=1, shuffle=False, num_workers=0)
        results = []
        for index, (case, batch) in enumerate(zip(cases, loader), 1):
            if progress:
                progress("preprocess:{}".format(case.case_id))
            net_args = [t.to(self.device).float() for t in batch[1:5]]
            fold_probs, mean_prob = self._predict_states(
                net, states, net_args, progress)
            pred = "Positive" if int(np.argmax(mean_prob)) == 1 else "Negative"
            results.append(ScanResult(
                case_id=case.case_id,
                prob_neg=float(mean_prob[0]),
                prob_pos=float(mean_prob[1]),
                prediction=pred,
                fold_probs=fold_probs,
            ))
            del net_args, batch
            if progress:
                progress("case:{}:{}:{}".format(case.case_id, index, len(cases)))
        return results

    def results_to_dataframe(self, results: list[ScanResult], labels: Optional[dict[str, str]] = None) -> pd.DataFrame:
        return scan_results_to_dataframe(results, labels)

    def cleanup(self):
        if self._scratch.exists():
            shutil.rmtree(self._scratch, ignore_errors=True)


def scan_results_to_dataframe(results: list[ScanResult],
                              labels: Optional[dict[str, str]] = None) -> pd.DataFrame:
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
        positive_votes = sum(
            1 for probs in r.fold_probs.values()
            if probs is not None and probs[1] > probs[0])
        negative_votes = sum(
            1 for probs in r.fold_probs.values()
            if probs is not None and probs[1] <= probs[0])
        row["Positive_folds"] = positive_votes
        row["Negative_folds"] = negative_votes
        row["Margin_from_0.5"] = round(abs(r.prob_pos - 0.5), 6)
        rows.append(row)
    return pd.DataFrame(rows)
