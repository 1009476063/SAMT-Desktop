"""Red regressions for the lossless checkpoint store inference path."""
from __future__ import annotations

import ctypes
import json
import shutil
import sys
import zipfile
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

import torch  # noqa: E402

from core.engine import InferenceEngine, build_checkpoint_store  # noqa: E402


def _tensor_bytes(tensor) -> bytes:
    storage = tensor.detach().cpu().contiguous().untyped_storage()
    return bytes((ctypes.c_ubyte * storage.nbytes()).from_address(
        storage.data_ptr()))


def _store(tmp_path: Path) -> tuple[Path, list[torch.Tensor], list[str]]:
    paths: list[Path] = []
    tensors: list[torch.Tensor] = []
    for index in range(10):
        tensor = torch.arange(4, dtype=torch.float32) + index
        tensors.append(tensor)
        path = tmp_path / "pathology_pretrain_fold{}_best_AUC_val.pth".format(
            index + 1)
        torch.save({"weight": tensor}, path)
        paths.append(path)
    target = tmp_path / "samt-checkpoints.zip"
    build_checkpoint_store(paths, target)
    with zipfile.ZipFile(target) as archive:
        names = list(json.loads(archive.read("manifest.json"))["state"])
    return target, tensors, names


class _RecordingNet:
    def __init__(self):
        self.loaded = []

    def to(self, _device):
        return self

    def eval(self):
        return self

    def load_state_dict(self, state):
        if not isinstance(state, dict):
            raise TypeError(
                "Expected state_dict to be dict-like, got <class '{}'>.".format(
                    type(state).__name__))
        self.loaded.append(state)


def _engine(models_dir: Path, retain: bool) -> InferenceEngine:
    engine = object.__new__(InferenceEngine)
    engine._torch_mod = torch
    engine.device = torch.device("cpu")
    engine._on_status = None
    engine.retain_checkpoints = retain
    engine.models_dir = models_dir
    engine._ckpt_paths = [models_dir / "samt-checkpoints.zip"]
    engine._checkpoint_states = {}
    engine._shared_net = None
    engine._nets_lock = __import__("threading").Lock()
    engine._pretrain_path = models_dir / "resnet_18_23dataset.pth"
    engine._pretrain_state = None
    engine._pretrain_lock = __import__("threading").Lock()
    engine._scratch = models_dir / "scratch"
    engine._scratch.mkdir(exist_ok=True)
    engine.cleanup = lambda: shutil.rmtree(engine._scratch, ignore_errors=True)
    engine._backend_probe_error = ""
    def build_networks():
        net, states = engine._construct_networks(
            torch, lambda **kwargs: _RecordingNet(), None)
        engine._shared_net = net
        engine._checkpoint_states = states
        return states

    engine._build_networks = build_networks
    return engine


def _loaded_states(engine: InferenceEngine, names: list[str]):
    net, states = engine._checkpoints()
    assert list(states) == names
    return net, states


def test_retained_store_states_are_dictionary_state_dicts(tmp_path):
    store, _, names = _store(tmp_path)
    engine = _engine(tmp_path, retain=True)

    net, states = _loaded_states(engine, names)

    # This is the exact load_state_dict call that failed after choosing
    # a directory in the shipped v1.3.0 batch workflow.
    for state in states.values():
        net.load_state_dict(state)
    assert len(net.loaded) == 10
    assert all(isinstance(state, dict) for state in net.loaded)
    engine.cleanup()


def test_retained_store_states_are_byte_identical_to_raw_weights(tmp_path):
    store, tensors, names = _store(tmp_path)
    engine = _engine(tmp_path, retain=True)

    _, states = _loaded_states(engine, names)

    for state, expected in zip(states.values(), tensors):
        assert _tensor_bytes(state["weight"]) == _tensor_bytes(expected)
    engine.cleanup()


def test_low_memory_store_keeps_ten_ordered_states(tmp_path):
    store, _, names = _store(tmp_path)
    engine = _engine(tmp_path, retain=False)

    _, states = _loaded_states(engine, names)

    assert len(states) == 10
    assert all(state == name for name, state in states.items())
    engine.cleanup()


def test_low_memory_store_rereads_every_dictionary_state_dict(tmp_path):
    store, tensors, names = _store(tmp_path)
    engine = _engine(tmp_path, retain=False)

    net, states = _loaded_states(engine, names)
    rebuilt = [
        engine._load_store_checkpoint(name) if isinstance(state, str)
        else state
        for name, state in states.items()
    ]

    assert all(isinstance(state, dict) for state in rebuilt)
    assert all(_tensor_bytes(state["weight"]) == _tensor_bytes(expected)
               for state, expected in zip(rebuilt, tensors))
    engine.cleanup()


def test_low_memory_raw_checkpoints_reread_every_state_dict(tmp_path):
    paths: list[Path] = []
    tensors: list[torch.Tensor] = []
    for index in range(10):
        tensor = torch.arange(4, dtype=torch.float32) + index
        tensors.append(tensor)
        path = tmp_path / "pathology_pretrain_fold{}_best_AUC_val.pth".format(
            index + 1)
        torch.save({"weight": tensor}, path)
        paths.append(path)
    engine = _engine(tmp_path, retain=False)
    engine._ckpt_paths = paths

    def build_networks():
        from core.engine import load_checkpoint_state
        net, states = engine._construct_networks(
            torch, lambda **kwargs: _RecordingNet(), load_checkpoint_state)
        engine._shared_net = net
        engine._checkpoint_states = states
        return states

    engine._build_networks = build_networks
    _, states = engine._checkpoints()

    assert list(states) == [path.name for path in paths]
    assert all(isinstance(state, Path) for state in states.values())
    loaded = []
    for name, state in states.items():
        if isinstance(state, Path):
            state = torch.load(str(state), map_location="cpu")
        elif isinstance(state, str) and name == state:
            state = engine._load_store_checkpoint(name)
        loaded.append(state)
    assert all(isinstance(state, dict) for state in loaded)
    for state, expected in zip(loaded, tensors):
        assert _tensor_bytes(state["weight"]) == _tensor_bytes(expected)
    engine.cleanup()
