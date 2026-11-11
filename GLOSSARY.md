# GLOSSARY

Terms are domain vocabulary only. Implementation detail lives in the code and ADRs.

## Case
One patient episode in the study cohort. Identified by `ID` in `CP.xlsx` and on disk.

## NSLN
Non-sentinel lymph node. Axillary lymph nodes beyond the sentinel node. The prediction target is whether NSLN metastasis is present.

## SLN
Sentinel lymph node. All cases in scope are SLN-positive; SLN counts are input features, not the target.

## DCE-MRI
Dynamic contrast-enhanced magnetic resonance imaging volume. Model input. The desktop app expects the N4-bias-corrected variant (`*_DCE_N4`).

## MLO
Mediolateral oblique mammography view. Model input.

## Decay mask
Spatial prior channel derived from `GTV` and `GTVnd1` contours: value 1 at the tumour core, decaying outward. Precomputed offline; the desktop app consumes, never generates, these files.

## Fold checkpoint
One trained model weight file from 5-fold cross-validation. Ten exist: five folds × two selection metrics.

## Ensemble
Arithmetic mean of per-class probabilities across all usable fold checkpoints. The default desktop prediction mode.

## Ensemble prediction
The class (Negative / Positive) chosen by the higher mean probability.

## Single-weight mode
Prediction using exactly one fold checkpoint, selected by fold number and metric.

## Experiment tree
The on-disk layout consumed by batch mode: `<root>/MRMG/<Label>/<ID>/…` images plus `<root>/CP.xlsx`.

## CP.xlsx
The structured clinical/pathology table (Sheet1) supplying 55 encoded features. Column names and values are contract; the app does not paraphrase them.

## Research use
The scope boundary of the entire application: no clinical decision support, no diagnostic claim. Enforced by the startup disclaimer.

## Reference backend
The CPU compute path used for exact numerical comparison with the experiment. CUDA and MPS are optional accelerators; their kernels may change last-digit probabilities.

## Low-memory mode
A runtime mode that rereads each fold checkpoint during inference instead of retaining all ten state dictionaries in memory. It does not change the ensemble or preprocessing.
