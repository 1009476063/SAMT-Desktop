"""v1.5.0 workflow, localization, and responsive-layout regressions."""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))


def _settings(language: str = "en-US"):
    return type("S", (), {
        "data": {"language": language},
        "save": lambda self: None,
    })()


def _window(monkeypatch, language: str = "en-US"):
    import ui.main_window as main_window

    monkeypatch.setattr(main_window, "Settings", lambda: _settings(language))
    monkeypatch.setattr(
        main_window.MainWindow, "_prepare_engine", lambda self: None)
    return main_window, main_window.MainWindow()


def test_seven_workflow_pages_and_preprocessing_is_independent(
        qt_app, monkeypatch):
    _, window = _window(monkeypatch)

    assert window.pages.count() == 7
    assert window.nav_group.buttons()[0].text() == "Preprocessing"
    assert not hasattr(window, "batch_prepare_btn")
    assert window.preprocess_run_btn.parent() is not window.pages.widget(2)

    source = inspect.getsource(__import__(
        "ui.main_window", fromlist=["InferThread"]).InferThread.run)
    assert "prepare_case_inputs" not in source
    assert "infer_staged_batch" in source
    window.close()


def test_single_and_batch_results_share_results_page(
        qt_app, monkeypatch):
    from core.engine import ScanResult

    _, window = _window(monkeypatch)
    single = ScanResult(
        "single_case", 0.491009, 0.508991, "Positive",
        {"fold_{}".format(index): [0.1, 0.9] for index in range(10)})
    batch = ScanResult(
        "batch_case", 0.186543, 0.813457, "Positive",
        {"fold_{}".format(index): [0.1, 0.9] for index in range(10)})
    window._single_case_for_run = SimpleNamespace(
        case_id="single_case", case_root=Path("/synthetic/single_case"))
    window._show_single_result(single)
    window.batch_results = [batch]
    window.batch_cases = [SimpleNamespace(
        case_id="batch_case", case_root=Path("/synthetic/batch_case"))]
    window._refresh_results()

    assert window.results_table.rowCount() == 2
    assert window.results_export_btn.isEnabled()
    assert "0.508991" in window.results_table.item(0, 2).text()
    assert "0.813457" in window.results_table.item(1, 2).text()
    window.close()


def test_standalone_viewer_resolves_the_selected_case(
        qt_app, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication

    _, window = _window(monkeypatch)
    first = tmp_path / "first_case"
    second = tmp_path / "second_case"
    first.mkdir()
    second.mkdir()
    window._case_rows = [
        SimpleNamespace(case_id="first_case", case_root=first),
        SimpleNamespace(case_id="second_case", case_root=second),
    ]
    window._refresh_viewer_cases()
    index = window.viewer_case_combo.findData(str(second))
    assert index >= 0
    window.viewer_case_combo.setCurrentIndex(index)
    QApplication.processEvents()
    assert window._viewer_selected_root() == second
    assert window.viewer_open_btn.isEnabled()
    window.close()


def test_all_pages_switch_language_at_runtime(qt_app, monkeypatch):
    from PySide6.QtWidgets import QApplication

    _, window = _window(monkeypatch)
    window.show()
    QApplication.processEvents()
    for page in range(window.pages.count()):
        window._navigate(page)
        QApplication.processEvents()
        window._apply_language("zh-CN")
        assert window.nav_group.buttons()[0].text() == "预处理"
        assert window.pages.widget(page) is not None
        window._apply_language("en-US")
        assert window.nav_group.buttons()[0].text() == "Preprocessing"
    window.close()


def test_pages_fit_desktop_and_minimum_window_sizes(
        qt_app, monkeypatch):
    from PySide6.QtWidgets import QApplication

    _, window = _window(monkeypatch)
    window.show()
    for width, height in ((1460, 900), (1180, 760)):
        window.resize(width, height)
        QApplication.processEvents()
        window._sync_single_layout()
        QApplication.processEvents()
        for page in range(window.pages.count()):
            window._navigate(page)
            QApplication.processEvents()
            scroll = window.pages.widget(page)
            assert scroll.widget().width() <= scroll.viewport().width()
    assert window.single_input_panel.width() == \
        window.single_workspace_panel.width()
    window.close()


def test_batch_headers_fit_their_columns_at_minimum_width(
        qt_app, monkeypatch):
    from PySide6.QtWidgets import QApplication

    _, window = _window(monkeypatch)
    window.resize(1180, 760)
    window.show()
    window._navigate(2)
    QApplication.processEvents()

    header = window.batch_table.horizontalHeader()
    assert header.sectionResizeMode(3) == header.ResizeMode.Fixed
    for column in range(window.batch_table.columnCount()):
        text = window.batch_table.horizontalHeaderItem(column).text()
        required = header.fontMetrics().horizontalAdvance(text) + 28
        assert window.batch_table.columnWidth(column) >= required, \
            "{} needs {} px, got {}".format(
                text, required, window.batch_table.columnWidth(column))
    window.close()
