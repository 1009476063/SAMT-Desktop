# SAMT Desktop

SAMT 前哨淋巴结阳性乳腺癌腋窝非前哨淋巴结转移智能预测系统（研究版）。A desktop wrapper for the SAMT NSLN metastasis research code.

**Research use only. Not for clinical decision making.**

## v1.3.1

This patch fixes the lossless checkpoint store inference path: retained and low-memory modes now pass all ten reconstructed state dictionaries to the shared network in their original order. It also replaces the flat path hint with a generic, copyable ASCII tree. The research-use consent version and all ten float32 weights are unchanged.

## v1.3.0

This release keeps the original experiment logic and ten-checkpoint ensemble while making the workbench generic, bilingual, and lighter at startup.

- The default interface is English. English and Chinese can be switched at runtime without restarting; consent, controls, validation messages, and result tables follow the active language immediately.
- A substantive, sectioned research-use consent gate is shown before the main window exists. Rejection or closing exits immediately, and a recorded current acceptance never flashes the gate again.
- The experiment root may have any name. It must contain `CP.xlsx` and `MRMG/` with disk-label and case folders holding the four NIfTI inputs. Selecting the root scans all cases; selecting a case folder resolves upward and scans only that case.
- Single-case mode can import a CP table, review the unique row and field coverage, fill the form unchanged, and preview a NIfTI middle slice. Batch mode shows required-input coverage for every case.
- The UI shell loads no pandas, NumPy, PyTorch, or SimpleITK modules. Preview and model dependencies load only on their corresponding actions; Pillow remains bundled because `pretrainedmodels` imports `torchvision` during network construction.
- The standalone gate keeps model loading after acceptance; existing byte-lossless checkpoint storage, CPU reference backend, and all ten float32 checkpoints are unchanged.
- CI builds a byte-lossless shared-tensor checkpoint store. Identical float32 tensors are stored once, saving about 182 MB; every reconstructed tensor is verified against the original checkpoints. Quantization, pruning, ONNX conversion, and reducing the 10-fold ensemble are deliberately excluded.
- Unused plotting/DICOM imports are removed from the inference import chain, and training-only packages are excluded from PyInstaller. PyTorch/MONAI imports and checkpoint preparation remain in a worker thread.
- A reorganized research workbench provides single-case input, batch validation, a 10-checkpoint result table, runtime controls, and method documentation in Chinese and English.
- CPU is the exact-reference backend. CUDA/MPS are opt-in, probed for the vendored 3D operators, and fall back to CPU when unsupported.
- The original `Dataset_img_clinical` preprocessing, four-modality network, and arithmetic mean of 10 fold probabilities are preserved. The v1.1.0 comparison against the original `infer.py --scan_all` remains the numerical baseline on the bundled `case1`: ensemble `P(neg)=0.4910087086`, `P(pos)=0.5089913145`.

## Layout

- `app/core/samt_core/` — vendored research code (see ADR 0003: fidelity over refactor)
- `app/core/engine.py` — staging + inference bridge
- `app/core/clinical_table.py` — CP.xlsx matching without feature re-encoding
- `app/ui/main_window.py` — PySide6 research workbench
- `app/ui/theme.py` — cross-platform Qt design tokens
- `app/locales/` — zh-CN / en-US JSON catalogs
- `app/core/experiment_contract.py` — generic on-disk input contract
- `app/core/contract_catalog.py` — lightweight directory and coverage scan
- `app/ui/image_preview.py` — action-local NIfTI preview
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

Use any study root with this generic structure. All root, disk-label, and case names are arbitrary:

```text
StudyRoot/
├── CP.xlsx
└── MRMG/
    └── <Label>/
        └── <CaseID>/
            ├── <CaseID>_DCE_N4.nii[.gz]
            ├── <CaseID>_DCE_decay1.nii[.gz]
            └── MG/
                ├── *<CaseID>*_MLO.nii[.gz]
                └── *<CaseID>*_MLO_decay1.nii[.gz]
```

To rebuild and verify the lossless checkpoint store locally:

```bash
python scripts/build_checkpoint_store.py
python scripts/verify_checkpoint_store.py
```

For numerical reproducibility, run the original experiment's `infer.py --task pathology_pretrain --scan_all` and compare each fold and the ensemble mean against the desktop result table. Do not replace the CPU reference with an accelerator when exact published probabilities are required.
