# Windows ARM64 build status

Date: 2026-11-11

## Decision
v1.0.0 ships macOS arm64 and Windows x64. Windows ARM64 is not shipped.

## Evidence
GitHub provides `windows-11-arm` hosted runners, including for private repositories. The blocker is the Python dependency chain, not runner availability:

- `torch` has no `win_arm64` wheel in any published release as of this check (2.3.0 included).
- `torchvision`, `monai`, and `SimpleITK` also have no published `win_arm64` wheels.
- The application requires all four at runtime; a shim or x64 emulation would not be a native ARM64 build and would change the supported runtime path.

A native build therefore requires building PyTorch and its dependencies from source for Windows ARM64, then re-validating that the 10 fold checkpoints produce the same probabilities. This is tracked as a separate engineering task; it is not a CI matrix toggle.

## GitHub asset size note
The Windows x64 ZIP exceeds GitHub's 2 GiB per-release-asset limit. The release workflow splits it into `SAMT-Desktop-Windows-x64.zip.part00` and `.part01`; `README-ASSETS.txt` documents how to rejoin them. The macOS arm64 ZIP is below the limit and is attached as a single file.
