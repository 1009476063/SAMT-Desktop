"""Original SAMT research code, vendored for desktop inference.

Preprocessing and feature encoding are intentionally left byte-for-byte
identical to the training-time implementation (dataset.py / utils.py).
"""
import sys
from pathlib import Path


def _ensure_importable() -> None:
    core_dir = str(Path(__file__).resolve().parent)
    if core_dir not in sys.path:
        sys.path.insert(0, core_dir)
