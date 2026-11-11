# ADR 0004: Visible startup and CPU reference backend

Date: 2026-11-11

## Status
Accepted

## Context
Version 1.0.1 opened a modal research-use disclaimer in the main window constructor, before `QMainWindow.show()`. On Windows the dialog could be covered by Explorer or system update windows; the hidden parent made the application appear not to launch. Separately, shell startup imported the research Dataset module eagerly, and clicking predict constructed ten full networks synchronously.

Accelerator kernels can alter floating-point reduction order. PyTorch 2.3 MPS also lacks `aten::max_pool3d_with_indices`, which is used by the vendored 3D backbone.

## Decision
- Show the main window before any modal research-use gate. Defer the gate to the event loop and explicitly raise and activate it, with Windows retries.
- Keep PyTorch/MONAI imports and checkpoint preparation in a worker thread so the shell is visible immediately.
- Default to CPU as the exact-reference backend. Expose CUDA/MPS as opt-in choices, probe the vendored network with a small forward pass, and rebuild on CPU when a kernel is missing.
- Preserve the 10-checkpoint arithmetic ensemble; performance work may only remove redundant construction, imports, and disk staging.

## Consequences
- First-run users always see a foreground, parented disclaimer with an explicit quit action.
- The original experiment probabilities remain the acceptance baseline. Backend options never silently reduce the ensemble.
- MPS on PyTorch 2.3 reports a CPU fallback instead of failing during the first case. CUDA acceleration remains available where the full operator set is supported.
- Language changes still require a restart because Qt widgets are constructed once; this is shown in the settings message.
