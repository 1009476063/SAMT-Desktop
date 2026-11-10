# ADR 0002: Fully offline packaging with bundled checkpoints

Date: 2026-11-11

## Status
Accepted

## Context
Two viable distribution models: thin shell downloading weights/dependencies at first run, or a large fully offline installer. Target users include hospital research environments with restricted internet.

## Decision
Bundle everything: PyInstaller onedir, torch/MONAI/SimpleITK runtime, all 10 fold checkpoints (~1.7 GB), and the 3D backbone pretrain weights. The vendored 2D backbone is constructed with `pretrained=None` so no code path fetches ImageNet weights at runtime.

## Consequences
- Installer/download size is roughly 2-3 GB per platform; accepted.
- First-run works with zero network; no download failure modes.
- Checkpoint updates ship as app updates rather than in-app downloads.
