# ADR 0005: Consent gate before UI and lossless-only size reduction

Date: 2026-11-13

## Status
Accepted

## Context
Showing the main window first made the research-use dialog depend on native foreground activation. On Windows it could still be covered by Explorer or update prompts. The shipped bundle is about 2.5 GB: 1.73 GB of fold checkpoints, 126 MB of 3D backbone weights, and large PyTorch/SimpleITK libraries. The published probabilities are an arithmetic mean over all ten float32 checkpoints.

## Decision
- Construct and show the standalone research-use gate before the `QMainWindow`, start model loading only after acceptance, and return immediately on rejection or close.
- Keep all ten checkpoints and float32 weights. Accept only byte-lossless size reductions: deduplicate identical tensor storage across checkpoints, remove unused plotting/DICOM imports from the runtime path, and exclude training-only packages from PyInstaller.
- Reject quantization, pruning, low-rank approximation, ONNX conversion, and reducing the ensemble unless a new experiment establishes equivalent probabilities.

## Consequences
- The acceptance version changes to 1.3.0 so every user explicitly sees the expanded startup gate. Once a matching acceptance is recorded, `has_current_consent` skips the dialog entirely on later launches.
- The checkpoint store reconstructs each state dict from raw tensor bytes plus dtype/shape metadata and verifies the payload digest. It saves about 182 MB without changing a single tensor value.
- The experiment root is arbitrary and must contain `CP.xlsx` plus `MRMG/<Label>/<ID>/`; no root name, label, or case ID is hardcoded. A selected case folder resolves upward and scans only that case, while selecting the root scans every case. CP.xlsx values remain the experiment contract; imported rows are reviewed before autofill.
- The UI shell, consent gate, and first paint import no pandas, NumPy, PyTorch, or SimpleITK modules. Preview dependencies load only when an image preview is requested. Runtime text stores translation keys so switching language updates open widgets without restarting.
- The related SLN Predictor project contributes workflow ideas only: unique patient matching, field review, and completeness feedback. Its Chen-Dai distance, location branches, and feature encoder belong to a different model and are not imported.
