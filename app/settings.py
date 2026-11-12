"""Persistent settings stored per-platform (Q6: standard app-data dir)."""
from __future__ import annotations

import json
import sys
from pathlib import Path


APP_NAME = "SAMT"


def settings_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming"
    else:
        base = Path.home() / ".config"
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULTS = {
    "language": "en-US",  # English is the default; users may switch to Chinese
    "disclaimer_accepted": False,
    "remember_consent": True,
    "models_dir": "",  # empty = bundled models dir
    "device": "cpu",  # CPU is the exact-reproduction reference
    "low_memory": False,
    "last_data_dir": "",
    "last_export_dir": "",
    "accepted_disclaimer_version": "",
}


class Settings:
    def __init__(self):
        self.path = settings_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        if self.path.is_file():
            try:
                self.data.update(json.loads(self.path.read_text("utf-8")))
            except Exception:
                pass

    def save(self):
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
