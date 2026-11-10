# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

PROJECT = Path(SPECPATH)
APP = PROJECT / "app"

a = Analysis(
    [str(APP / "main.py")],
    pathex=[str(APP)],
    binaries=[],
    datas=[
        (str(APP / "locales"), "locales"),
        (str(APP / "core" / "samt_core" / "Networks" / "resnet_18_23dataset.pth"),
         "core/samt_core/Networks"),
    ],
    hiddenimports=[
        "monai", "monai.transforms", "monai.data",
        "pretrainedmodels", "SimpleITK", "skimage", "openpyxl", "six",
    ],
    excludes=["tkinter", "PyQt5", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SAMT-Desktop",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SAMT-Desktop",
)
