"""Shared test environment and deterministic offscreen Qt lifecycle."""
from __future__ import annotations

import os

import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


_QT_APP = None


@pytest.fixture(scope="session")
def qt_app():
    """Own one QApplication for the whole session.

    Repeatedly rebinding ``QApplication.instance()`` in individual tests can
    leave Python wrappers sharing the same C++ object, which crashes while
    PySide tears down the test process.
    """
    global _QT_APP
    from PySide6.QtWidgets import QApplication

    _QT_APP = QApplication.instance() or QApplication([])
    _QT_APP.setQuitOnLastWindowClosed(False)
    return _QT_APP


def _flush_qt_deletions():
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication

    for widget in QApplication.topLevelWidgets():
        try:
            widget.close()
            widget.deleteLater()
        except RuntimeError:
            pass
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    QCoreApplication.processEvents()


@pytest.fixture(autouse=True)
def _cleanup_qt_after_test(qt_app):
    """Let Qt, not Python's finalizer order, destroy each test's widgets."""
    yield qt_app
    _flush_qt_deletions()


def pytest_sessionfinish(session, exitstatus):
    """Destroy test widgets while their owning QApplication still exists."""
    if _QT_APP is None:
        return
    _flush_qt_deletions()
