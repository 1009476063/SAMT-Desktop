import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP))

from i18n import I18n  # noqa: E402


def test_both_locales_have_all_keys():
    zh = I18n("zh-CN")
    en = I18n("en-US")
    assert set(zh._catalogs["zh-CN"].keys()) == set(en._catalogs["en-US"].keys())


def test_formatting():
    zh = I18n("zh-CN")
    assert "3" in zh.tr("batch.found", n=3)
