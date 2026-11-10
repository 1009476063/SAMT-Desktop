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
