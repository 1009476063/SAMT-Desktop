# SAMT Desktop

SAMT 乳腺淋巴结转移预测系统（研究版） — a desktop wrapper for the SAMT NSLN metastasis research code.

**Research use only. Not for clinical decision making.**

## Layout

- `app/core/samt_core/` — vendored research code (see ADR 0003: fidelity over refactor)
- `app/core/engine.py` — staging + inference bridge
- `app/ui/main_window.py` — PySide6 UI (single-case wizard, batch table, settings, about)
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

They are copied from the original experiment package and are intentionally not tracked in Git. The CI workflow expects them to be present in the checkout (e.g. via Git LFS or a private artifact download step added by the repository owner).
