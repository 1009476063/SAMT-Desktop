# ADR 0007: Derive offline products without replacing supplied inputs

Date: 2026-11-14

## Status
Accepted

## Context
The research model consumes four images: N4-corrected DCE, a DCE decay mask,
MLO, and an MLO decay mask. Earlier releases required operators to run
`N4BiasFieldCorrection` and `get_SAmask.py` separately. A single raw DCE volume
cannot determine the independent MLO view, tumour/lymph-node contours, or the
clinical and pathology variables; fabricating those inputs would change the
experiment.

The sample `*_DCE_N4.nii.gz` files are voxel-identical to raw DCE but not
byte-identical, so a regenerated N4 image is not interchangeable with the
supplied product for exact probability reproduction.

## Decision
The workbench distinguishes Source images from Derived products. It generates
only missing N4 and decay files, using the experiment's filter defaults and
formulas, including trailing-singleton-plane MLO contours. It also derives an
empty ALN diameter cell into a staged copy of `CP.xlsx`. Existing N4 and decay
products are passed through untouched and always take priority. MLO images,
contours, and clinical rows remain explicit operator inputs.

The ten-checkpoint ensemble, feature encoding, and staging layout are
unchanged. A staged clinical workbook is used only when all selected cases
refer to the same staged copy.

## Consequences
- A complete source-data folder can run without separate offline scripts.
- Published probabilities remain reproducible when supplied products are kept:
  CPU reference `case1 P(pos)=0.508991314`, `case2 P(pos)=0.813457018`.
- Regenerating N4 from raw DCE is a distinct input and may yield a different
  probability; the UI documents this provenance boundary.
- Regression tests compare both DCE and MLO decay outputs against the original
  experiment formula and preserve the source volumes and workbook.
