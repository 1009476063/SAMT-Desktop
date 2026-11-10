"""Tiny JSON-backed translation helper."""
from __future__ import annotations

import json
import locale
from pathlib import Path


LOCALES_DIR = Path(__file__).resolve().parent / "locales"
SUPPORTED = ("zh-CN", "en-US")


class I18n:
    def __init__(self, lang: str = ""):
        self._catalogs = {}
        for code in SUPPORTED:
            try:
                self._catalogs[code] = json.loads(
                    (LOCALES_DIR / f"{code}.json").read_text("utf-8"))
            except Exception:
                self._catalogs[code] = {}
        self.lang = lang if lang in SUPPORTED else self._system_lang()

    @staticmethod
    def _system_lang() -> str:
        try:
            code = locale.getdefaultlocale()[0] or ""
        except Exception:
            code = ""
        return "zh-CN" if code.lower().startswith("zh") else "en-US"

    def tr(self, key: str, **kwargs) -> str:
        text = self._catalogs.get(self.lang, {}).get(key) \
            or self._catalogs["en-US"].get(key) or key
        return text.format(**kwargs) if kwargs else text
