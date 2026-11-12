#!/usr/bin/env python3
"""Build a byte-lossless shared-tensor store from the 10 SAMT checkpoints."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))

from core.engine import build_checkpoint_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, default=ROOT / "app" / "models")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "app" / "models" / "samt-checkpoints.zip")
    args = parser.parse_args()
    paths = sorted(args.models.glob("pathology_pretrain_fold*_*.pth"))
    result = build_checkpoint_store(paths, args.output)
    result["output"] = str(args.output)
    result["output_bytes"] = args.output.stat().st_size
    result["saved_bytes"] = (result["raw_tensor_bytes"] -
                             result["unique_tensor_bytes"])
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
