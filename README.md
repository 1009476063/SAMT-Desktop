# SAMT Desktop

SAMT 前哨淋巴结阳性乳腺癌腋窝非前哨淋巴结转移智能预测系统（研究版）。A desktop wrapper for the SAMT NSLN metastasis research code.

**Research use only. Not for clinical decision making.**

## v1.1.1

- This patch fixes a Windows-only staging-path assertion in CI. Runtime code, preprocessing, and probability arithmetic are unchanged.
- Startup shows the main window first, then presents an always-on-top research-use disclaimer. Heavy PyTorch/MONAI imports and checkpoint preparation run in a worker thread.
- A reorganized research workbench provides single-case input, batch validation, a 10-checkpoint result table, runtime controls, and method documentation in Chinese and English.
- CPU is the exact-reference backend. CUDA/MPS are opt-in, probed for the vendored 3D operators, and fall back to CPU when unsupported.
- The original `Dataset_img_clinical` preprocessing, four-modality network, and arithmetic mean of 10 fold probabilities are preserved. The v1.1.0 comparison against the original `infer.py --scan_all` remains the reference for v1.1.1 on the bundled `case1`: ensemble `P(neg)=0.4910087086`, `P(pos)=0.5089913145`.

## Layout

- `app/core/samt_core/` — vendored research code (see ADR 0003: fidelity over refactor)
- `app/core/engine.py` — staging + inference bridge
- `app/ui/main_window.py` — PySide6 research workbench
- `app/ui/theme.py` — cross-platform Qt design tokens
- `app/locales/` — zh-CN / en-US JSON catalogs
- `app/models/` — 10 fold checkpoints (not in Git; see below)
- `packaging/` — PyInstaller specs
- `.github/workflows/build.yml` — macOS arm64 + Windows x64 builds

## Checkpoints

The 10 fold checkpoints (~1.7 GB) live in `app/models/` with the shipped naming scheme:

```
pathology_pretrain_fold{1..5}_best_AUC_val.pth
pathology_pretrain_fold{1..5}_best_ACC_val.pth
```

They are copied from the original experiment package and are intentionally not tracked in Git. CI downloads them from the private `checkpoints-v1` release before running tests and PyInstaller.

## Verification

```bash
python -m pytest tests -q
QT_QPA_PLATFORM=offscreen python app/main.py
```

For numerical reproducibility, run the original experiment's `infer.py --task pathology_pretrain --scan_all` and compare each fold and the ensemble mean against the desktop result table. Do not replace the CPU reference with an accelerator when exact published probabilities are required.
