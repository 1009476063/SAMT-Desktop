"""Tiny JSON-backed translation helper."""
from __future__ import annotations

import json
from pathlib import Path


LOCALES_DIR = Path(__file__).resolve().parent / "locales"
SUPPORTED = ("zh-CN", "en-US")


class I18n:
    def __init__(self, lang: str = "en-US"):
        self._catalogs = {}
        for code in SUPPORTED:
            try:
                self._catalogs[code] = json.loads(
                    (LOCALES_DIR / f"{code}.json").read_text("utf-8"))
            except Exception:
                self._catalogs[code] = {}
        self.lang = lang if lang in SUPPORTED else "en-US"

    def set_language(self, lang: str):
        """Switch the active catalog without rebuilding any widgets."""
        if lang in SUPPORTED and lang != self.lang:
            self.lang = lang

    def tr(self, key: str, **kwargs) -> str:
        fallback = kwargs.pop("fallback", None)
        text = self._catalogs.get(self.lang, {}).get(key) \
            or self._catalogs["en-US"].get(key) or fallback or key
        return text.format(**kwargs) if kwargs else text
