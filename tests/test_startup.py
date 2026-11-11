"""Regression tests for the first-run window lifecycle and engine loading."""
import ast
import sys
from pathlib import Path


APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))


def _source(name: str) -> str:
    return (APP / name).read_text("utf-8")


def test_main_shows_window_before_startup_gate():
    source = _source("main.py")
    tree = ast.parse(source)
    calls = [
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert calls.index("show") < calls.index("start")


def test_disclaimer_uses_foreground_and_deferred_display():
    source = _source("ui/main_window.py")
    assert "QTimer.singleShot(0, self._show_disclaimer_if_needed)" in source
    assert "WindowStaysOnTopHint" in source
    assert "activateWindow()" in source
    assert "self._force_foreground()" in source


def test_engine_is_outside_shell_import_chain():
    engine_source = _source("core/engine.py")
    assert "from .samt_core.dataset import Dataset_img_clinical" in engine_source
    assert "def _build_loader" in engine_source
    shell_source = _source("ui/main_window.py")
    assert "InferenceEngine" not in shell_source.split("class EngineInitThread")[0]


def test_worker_threads_are_not_qt_parented_to_closing_window():
    source = _source("ui/main_window.py")
    assert "super().__init__()" in source
    assert "self._closing = True" in source
    assert "thread.wait()" in source


def test_macos_resources_models_path_is_discovered():
    source = _source("ui/main_window.py")
    assert 'APP_DIR.parent / "Resources"' in source
    assert '(resources / "models")' in source
