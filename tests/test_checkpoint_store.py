import ctypes
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

import torch  # noqa: E402

from core.engine import (  # noqa: E402
    build_checkpoint_store, load_stored_checkpoint,
)


def _tensor_bytes(tensor) -> bytes:
    storage = tensor.detach().cpu().contiguous().untyped_storage()
    return bytes((ctypes.c_ubyte * storage.nbytes()).from_address(
        storage.data_ptr()))


def test_deduplicated_store_rebuilds_byte_identical_state(tmp_path):
    paths = []
    for index in range(10):
        path = tmp_path / "pathology_pretrain_fold{}_best_AUC_val.pth".format(
            index + 1)
        torch.save({
            "shared": torch.arange(12, dtype=torch.float32).reshape(3, 4),
            "unique": torch.full((2,), float(index), dtype=torch.float32),
            "flag": torch.tensor(index, dtype=torch.int64),
        }, path)
        paths.append(path)
    target = tmp_path / "samt-checkpoints.zip"
    stats = build_checkpoint_store(paths, target)
    assert stats["unique_tensors"] == 21
    assert target.stat().st_size < sum(p.stat().st_size for p in paths)
    rebuilt = load_stored_checkpoint(target, paths[0].name)
    for key, value in torch.load(str(paths[0]), map_location="cpu").items():
        assert value.dtype == rebuilt[key].dtype
        assert value.shape == rebuilt[key].shape
        assert _tensor_bytes(value) == _tensor_bytes(rebuilt[key])
