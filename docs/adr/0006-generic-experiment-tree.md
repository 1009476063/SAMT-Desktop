# ADR 0006: Generic experiment tree and lightweight UI boundary

The vendored `Dataset_img_clinical` globs depend on the relative layout beneath a study root, not on a root named `NSLN` or on a case named `case2`. We accept any root containing `CP.xlsx` and `MRMG/<Label>/<ID>/`, scan all cases from the root, and scan only one case when its folder is selected. The UI shell keeps pandas, NumPy, PyTorch, and SimpleITK out of its import chain; field coverage and image preview are verification aids that never alter the four model inputs.
