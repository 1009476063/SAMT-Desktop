# ADR 0003: Fidelity over refactor in the vendored core

Date: 2026-11-11

## Status
Accepted

## Context
The research code (dataset.py etc.) contains known oddities: hardcoded feature constants, substring-based encoders, a hardcoded Axillary-MRI one-hot vector. The desktop app could "clean" these, but the 10 checkpoints were trained against exactly this encoding.

## Decision
Vendor `dataset.py`, `utils.py`, `Nii_utils.py`, `Multimodal_Fusion_Network.py`, `ResNet_3D.py` and `Networks/` essentially verbatim. Only mechanical changes are allowed: import-path robustness and removing the network fetch in the 2D backbone. Any semantic change is forbidden without re-validating checkpoints.

## Consequences
- Predictions match the published pipeline bit-for-bit in intent (same preprocessing, same encoding).
- Known code smells remain; they are documented in the analysis doc, not fixed here.
- Future retraining changes must flow into `samt_core` deliberately, not via casual edits.

## Verification note (v1.1.0)
The desktop shell preserves `Dataset_img_clinical` preprocessing and the
10-checkpoint arithmetic mean. A CPU smoke comparison on the bundled `case1`
sample produced ensemble probabilities `0.4910087086 / 0.5089913145`,
matching the original `infer.py --scan_all` output to its four printed
decimals, with every individual fold probability also aligned.

Performance changes are outside the numerical path: heavy imports are
deferred, one constructed network is reused by loading each checkpoint's
state_dict in turn, checkpoint staging uses hard links for the four model
inputs, and one CP.xlsx is written per batch.
CPU remains the exact-reference default. CUDA/MPS are opt-in and undergo a
small forward probe; unsupported vendored 3D operators rebuild on CPU.
