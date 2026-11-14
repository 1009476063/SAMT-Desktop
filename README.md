# SAMT Desktop

SAMT 前哨淋巴结阳性乳腺癌腋窝非前哨淋巴结转移智能预测系统（研究版）。A desktop wrapper for the SAMT NSLN metastasis research code.

**Research use only. Not for clinical decision making.**

## v1.4.0

This release adds source-image preparation, six-decimal borderline-result reporting, a blank default clinical form, and a restyled workbench. The network, ten-checkpoint ensemble, and supplied-input inference probabilities are unchanged.

- A case folder can start with `DCE_N4` or raw DCE, paired DCE GTV/GTVnd1 contours, MLO, and paired MLO GTV/GTVnd1 contours. Existing `DCE_N4` files are used byte-for-byte. The workbench derives both `decay1` masks, including trailing-singleton-plane MLO contours, and derives the lowest-layer ALN diameter into a staged copy of `CP.xlsx`; a missing N4 image is generated with the exact `Nii_utils.N4BiasFieldCorrection` filter. The source workbook is never modified.
- Because the supplied sample `*_DCE_N4.nii.gz` files are byte-different but voxel-identical to their raw DCE counterparts, regenerating N4 for those samples is not numerically equivalent to reusing the supplied files. Keep the supplied `DCE_N4` inputs when reproducing the published probabilities. With supplied products reused, the CPU reference returns `case1 P(pos)=0.508991314` and `case2 P(pos)=0.813457018`.
- Borderline ensemble results retain six decimals, show `50.8991%`, the ten-checkpoint vote split, and the exact margin from 0.5. Exported CSV includes `Positive_folds`, `Negative_folds`, and `Margin_from_0.5`.
- Single-case clinical and pathology fields all start empty. Selecting a case source folder fills only the derived ALN diameter; importing a clinical table remains an explicit user action.
- N4/decay preparation runs off the UI thread with localized phase messages. The batch result table has a fixed-width image-viewer column and a visible critical-result note.

## v1.3.2

This release completes the batch workflow and adds a read-only image viewer without changing preprocessing, the network, the ten-checkpoint ensemble, or prediction probabilities.

- The batch directory is always empty at startup and stays session-only. A legacy saved directory is ignored and removed from settings; no machine-specific path is shown or bundled.
- Starting inference immediately shows a localized started message and 0%. The progress bar reports percentage completion across all cases and all ten checkpoints, including preprocessing, checkpoint, and case-level state. Completion shows a visible result summary and enables CSV export.
- The completion callback now imports the result converter at the engine boundary, so results, the selected-case summary, per-case input buttons, and CSV export are no longer interrupted by a `NameError`.
- Batch results show `P(negative)`, `P(positive)`, and the localized ensemble class in the correct columns. Selecting a row shows the probabilities with six decimal places, the usable checkpoint count, and the source-file entry point; all visible result text follows runtime language switches.
- The workbench can browse complete volumes: axial, coronal, and sagittal planes with slice sliders, previous/next controls, fit-to-window, and switching among the four model inputs. Two-dimensional MLO images open as a single plane. Heavy image libraries are imported only when a viewer is opened.
- A regression suite reproduces the v1.3.1 workflow defects before the fix. Full source tests, checkpoint byte-equivalence checks, locale key parity, and offscreen Qt checks pass locally.

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
- `app/core/preprocessing.py` — source-data preparation and offline product derivation
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

They are copied from the original experiment package and are intentionally not tracked in Git. CI downloads them from the repository's `checkpoints-v1` release before running tests and PyInstaller.

## Verification

```bash
python -m pytest tests -q
QT_QPA_PLATFORM=offscreen python app/main.py
```

Use any study root with this source-data structure. All root, disk-label, and case names are arbitrary. Existing model products always take priority; the two `decay1` masks are generated automatically:

```text
StudyRoot/
├── CP.xlsx
└── MRMG/
    └── <Label>/
        └── <CaseID>/
            ├── <CaseID>_DCE_N4.nii[.gz]  (or <CaseID>_DCE.nii[.gz])
            ├── <CaseID>_DCE_GTV.nii[.gz]
            ├── <CaseID>_DCE_GTVnd1.nii[.gz]
            └── MG/
                ├── *<CaseID>*_MLO.nii[.gz]
                ├── *<CaseID>*_MLO_GTV.nii[.gz]
                └── *<CaseID>*_MLO_GTVnd1.nii[.gz]
```

To rebuild and verify the lossless checkpoint store locally:

```bash
python scripts/build_checkpoint_store.py
python scripts/verify_checkpoint_store.py
```

For numerical reproducibility, run the original experiment's `infer.py --task pathology_pretrain --scan_all` and compare each fold and the ensemble mean against the desktop result table. Do not replace the CPU reference with an accelerator when exact published probabilities are required.
