# ADR 0005: Consent gate before UI and lossless-only size reduction

Date: 2026-11-12

## Status
Accepted

## Context
Showing the main window first made the research-use dialog depend on native foreground activation. On Windows it could still be covered by Explorer or update prompts. The shipped bundle is about 2.5 GB: 1.73 GB of fold checkpoints, 126 MB of 3D backbone weights, and large PyTorch/SimpleITK libraries. The published probabilities are an arithmetic mean over all ten float32 checkpoints.

## Decision
- Construct and show the standalone research-use gate before the `QMainWindow`, start model loading only after acceptance, and return immediately on rejection or close.
- Keep all ten checkpoints and float32 weights. Accept only byte-lossless size reductions: deduplicate identical tensor storage across checkpoints, remove unused plotting/DICOM imports from the runtime path, and exclude training-only packages from PyInstaller.
- Reject quantization, pruning, low-rank approximation, ONNX conversion, and reducing the ensemble unless a new experiment establishes equivalent probabilities.

## Consequences
- The acceptance version changes to 1.2.0 so every user explicitly sees the new startup gate.
- The checkpoint store reconstructs each state dict from raw tensor bytes plus dtype/shape metadata and verifies the payload digest. It saves about 182 MB without changing a single tensor value.
- Accepting a folder beneath `MRMG/<Label>/<ID>` resolves the experiment root automatically and scans only that case. CP.xlsx values remain the experiment contract; imported rows are reviewed before autofill.
- The related SLN Predictor project contributes workflow ideas only: unique patient matching, field review, and completeness feedback. Its Chen-Dai distance, location branches, and feature encoder belong to a different model and are not imported.
