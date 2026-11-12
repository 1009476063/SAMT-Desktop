#!/usr/bin/env python3
"""Compare every state-dict tensor in a store against the original .pth files."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

import numpy as np  # noqa: E402
import torch  # noqa: E402


def tensor_bytes(tensor) -> bytes:
    return tensor.detach().cpu().numpy().tobytes()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, default=ROOT / "app" / "models")
    parser.add_argument("--store", type=Path,
                        default=ROOT / "app" / "models" / "samt-checkpoints.zip")
    args = parser.parse_args()
    with zipfile.ZipFile(args.store) as archive:
        manifest = archive.read("manifest.json")
        payload = archive.read("tensors.bin")
    info = json.loads(manifest)
    if hashlib.sha256(payload).hexdigest() != info["tensor_sha256"]:
        raise SystemExit("tensor payload digest mismatch")
    tensors = []
    offset = 0
    for item in info["blobs"]:
        length = int(item["size"])
        array = np.frombuffer(payload[offset:offset + length],
                              dtype=np.dtype(item["dtype"]))
        tensors.append(torch.from_numpy(array.copy()).reshape(item["shape"]).clone())
        offset += length
    for path in sorted(args.models.glob("pathology_pretrain_fold*_*.pth")):
        original = torch.load(str(path), map_location="cpu")
        rebuilt = {key: tensors[int(index)] for key, index in
                   info["state"][path.name].items()}
        assert set(original) == set(rebuilt), path
        for key, value in original.items():
            assert value.dtype == rebuilt[key].dtype, (path, key, "dtype")
            assert value.shape == rebuilt[key].shape, (path, key, "shape")
            assert tensor_bytes(value) == tensor_bytes(rebuilt[key]), \
                (path, key, "bytes")
        print("identical:", path.name, len(original), "tensors")
    print("all 10 checkpoint state dictionaries are byte-identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
