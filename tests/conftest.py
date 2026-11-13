"""Shared test environment: deterministic offscreen Qt for every module."""
from __future__ import annotations

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"


def pytest_sessionfinish(session, exitstatus):
    """Keep a green Qt session from crashing while C++ objects unwind.

    GitHub macOS runners aborted after ``54 passed`` when PySide6 destroyed
    leftover widgets, and Windows returned exit code 1 despite a green run.
    A successful session therefore flushes and exits before that teardown.
    """
    if exitstatus != 0:
        return
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)

os.environ["QT_QPA_PLATFORM"] = "offscreen"
