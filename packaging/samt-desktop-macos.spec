# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

PROJECT = Path(SPECPATH).resolve().parent
APP = PROJECT / "app"
CORE = APP / "core" / "samt_core"

a = Analysis(
    [str(APP / "main.py")],
    pathex=[str(APP), str(CORE)],
    binaries=[],
    datas=[
        (str(APP / "locales"), "locales"),
        (str(APP / "models"), "models"),
        (str(APP / "core" / "samt_core" / "Networks" / "resnet_18_23dataset.pth"),
         "core/samt_core/Networks"),
    ],
    hiddenimports=[
        "monai", "monai.transforms", "monai.data",
        "pretrainedmodels", "SimpleITK", "nibabel", "scipy", "skimage",
        "openpyxl", "six",
        "torchvision", "torchvision.transforms", "PIL", "PIL.Image",
        "ui.main_window", "ui.theme", "core.engine", "core.preprocessing",
        # samt_core's flat imports (from Nii_utils import ...) resolve as
        # top-level modules at runtime via sys.path injection, so they must
        # be collected as top-level modules too.
        "Nii_utils", "utils", "dataset", "ResNet_3D", "Multimodal_Fusion_Network",
    ],
    excludes=["tkinter", "PyQt5", "IPython", "matplotlib", "pydicom",
              "sklearn", "tensorboardX", "pytest"],
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

app = BUNDLE(
    coll,
    name="SAMT-Desktop.app",
    icon=None,
    bundle_identifier="com.samt.desktop.research",
    version="1.4.1",
    info_plist={
        "CFBundleName": "SAMT Desktop",
        "CFBundleDisplayName": "SAMT Desktop",
        "CFBundleExecutable": "SAMT-Desktop",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.4.1",
        "CFBundleVersion": "1.4.1",
        "LSMinimumSystemVersion": "11.0",
        "NSHighResolutionCapable": True,
        "LSBackgroundOnly": False,
    },
)
