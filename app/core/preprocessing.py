"""Generate the experiment's offline products from operator-supplied images.

This module reproduces the source package's ``N4BiasFieldCorrection`` and the
DCE/MLO ``decay1`` formulas with the same filter defaults, output precision,
and NIfTI affine/header handling. Existing experiment products are never
overwritten; they remain the exact input to ``Dataset_img_clinical``.
"""
from __future__ import annotations

import glob
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


class PreprocessingError(ValueError):
    """Raised when an offline product cannot be derived faithfully."""


Progress = Callable[[str], None]

ALN_DIAMETER_COLUMN = "max diameter with lowest layer of ALN"


@dataclass(frozen=True)
class SourceInputs:
    """Source images that cannot be inferred from one raw DCE volume."""

    dce_raw: Path | None = None
    dce_n4: Path | None = None
    dce_decay: Path | None = None
    dce_gtv: Path | None = None
    dce_gtvnd1: Path | None = None
    mlo: Path | None = None
    mlo_decay: Path | None = None
    mlo_gtv: Path | None = None
    mlo_gtvnd1: Path | None = None


@dataclass
class PreparedInputs:
    """Resolved model inputs and the products generated for this run."""

    dce_n4: Path | None
    dce_decay: Path | None
    mlo: Path | None
    mlo_decay: Path | None
    generated: tuple[str, ...] = ()
    messages: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return all((self.dce_n4, self.dce_decay, self.mlo, self.mlo_decay))

    @property
    def model_inputs(self) -> dict[str, Path]:
        result = {}
        for key, value in (("DCE_N4", self.dce_n4),
                           ("DCE_decay1", self.dce_decay),
                           ("MLO", self.mlo),
                           ("MLO_decay1", self.mlo_decay)):
            if value is not None:
                result[key] = Path(value)
        return result


def _first(root: Path, pattern: str) -> Path | None:
    hits = sorted(glob.glob(str(root / pattern)))
    return Path(hits[0]) if hits else None


def lowest_layer_aln_diameter(contour: str | Path) -> float | None:
    """Reproduce the bottom-slice maximum-diameter step of CP preparation."""
    import SimpleITK as sitk
    import numpy as np
    from scipy.spatial.distance import pdist

    image = sitk.ReadImage(str(contour))
    volume = sitk.GetArrayFromImage(image)
    if volume.ndim != 3:
        raise PreprocessingError("dimension:DCE_GTVnd1")
    spacing = np.asarray(
        (image.GetSpacing()[2], image.GetSpacing()[1],
         image.GetSpacing()[0]), dtype=np.float32)
    occupied = np.argwhere(volume > 0)
    if not len(occupied):
        return None
    bottom = int(occupied[:, 0].min())
    points = np.argwhere(volume[bottom] > 0)
    if not len(points):
        return None
    physical = points * np.asarray((spacing[1], spacing[2]))
    if len(physical) == 1:
        value = math.hypot(float(spacing[1]), float(spacing[2]))
    else:
        value = float(np.max(pdist(physical)))
    return round(value, 2)


def find_source_inputs(case_root: Path, case_id: str) -> SourceInputs:
    """Locate both ready-made model inputs and their derivable sources."""
    root = Path(case_root)
    mg = root / "MG"
    return SourceInputs(
        dce_raw=_first(root, "{}_DCE.nii*".format(case_id)),
        dce_n4=_first(root, "{}_DCE_N4.nii*".format(case_id)),
        dce_decay=_first(root, "{}_DCE_decay1.nii*".format(case_id)),
        dce_gtv=_first(root, "{}_DCE_GTV.nii*".format(case_id)),
        dce_gtvnd1=_first(root, "{}_DCE_GTVnd1.nii*".format(case_id)),
        mlo=find_mlo_image(root, case_id),
        mlo_decay=_first(mg, "*{}_*MLO_decay1.nii*".format(case_id)),
        mlo_gtv=_first(mg, "*{}_*MLO_GTV.nii*".format(case_id)),
        mlo_gtvnd1=_first(mg, "*{}_*MLO_GTVnd1.nii*".format(case_id)),
    )


def find_mlo_image(case_root: Path, case_id: str) -> Path | None:
    """Exclude contour and decay files from the MLO source-image glob."""
    hits = sorted(glob.glob(str(Path(case_root) / "MG" /
                                "*{}_*MLO.nii*".format(case_id))))
    for hit in hits:
        name = Path(hit).name
        if "_GTV" not in name and "_decay" not in name:
            return Path(hit)
    return None


def prepare_clinical_table(root: str | Path,
                           target: str | Path | None = None
                           ) -> tuple[Path, int]:
    """Fill only empty ALN-diameter cells from DCE_GTVnd1 contours.

    The source workbook is never modified. A staged copy is written for the
    Dataset loader when at least one value is derived.
    """
    import pandas as pd

    root = Path(root)
    source = root / "CP.xlsx"
    if not source.is_file():
        raise PreprocessingError("missing:CP.xlsx")
    try:
        sheets = pd.ExcelFile(source).sheet_names
        sheet = "Sheet1" if "Sheet1" in sheets else sheets[0]
        frame = pd.read_excel(source, sheet_name=sheet, dtype=object)
    except Exception as exc:
        raise PreprocessingError("unreadable:CP.xlsx") from exc
    column = ALN_DIAMETER_COLUMN
    column_added = column not in frame.columns
    if column_added:
        insert_at = frame.columns.get_loc("ALND Status") \
            if "ALND Status" in frame.columns else len(frame.columns)
        frame.insert(insert_at, column, None)
    filled = 0
    for index, row in frame.iterrows():
        value = row.get(column)
        if value is not None and not (isinstance(value, float) and
                                      math.isnan(value)) and str(value).strip():
            continue
        case_id = str(row.get("ID", "")).strip()
        if not case_id or case_id.lower() == "nan":
            continue
        matches = []
        for label in sorted((root / "MRMG").glob("*")
                            if (root / "MRMG").is_dir() else ()):
            if label.is_dir():
                matches.extend(sorted(glob.glob(str(
                    label / case_id /
                    "{}_DCE_GTVnd1.nii*".format(case_id)))))
        if not matches:
            continue
        derived = lowest_layer_aln_diameter(matches[0])
        if derived is not None:
            frame.at[index, column] = derived
            filled += 1
    if target is None or not (filled or column_added):
        return source, 0
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(target, sheet_name=sheet, index=False)
    return target, filled if filled else 1


def source_problems(case_root: str | Path, case_id: str) -> tuple[str, ...]:
    """Return stable codes for source data that cannot be auto-generated."""
    root = Path(case_root)
    found = find_source_inputs(root, case_id)
    mlo = find_mlo_image(root, case_id) or found.mlo
    problems = []
    if found.dce_n4 is None and found.dce_raw is None:
        problems.append("source.dce")
    if found.dce_decay is None and not (
            found.dce_gtv and found.dce_gtvnd1):
        problems.append("source.dce_gtv")
    if mlo is None:
        problems.append("source.mlo")
    if found.mlo_decay is None and not (
            found.mlo_gtv and found.mlo_gtvnd1):
        problems.append("source.mlo_gtv")
    return tuple(problems)


def derivable_products(case_root: str | Path,
                       case_id: str) -> tuple[str, ...]:
    """Names of offline products that can be generated from source files."""
    found = find_source_inputs(Path(case_root), case_id)
    products = []
    if found.dce_n4 is None and found.dce_raw is not None:
        products.append("DCE_N4")
    if found.dce_decay is None and found.dce_gtv and found.dce_gtvnd1:
        products.append("DCE_decay1")
    if found.mlo_decay is None and found.mlo_gtv and found.mlo_gtvnd1:
        products.append("MLO_decay1")
    return tuple(products)


def n4_bias_correction(source: str | Path, target: str | Path) -> Path:
    """Reproduce ``Nii_utils.N4BiasFieldCorrection`` exactly."""
    import SimpleITK as sitk

    source = Path(source)
    target = Path(target)
    if not source.is_file():
        raise PreprocessingError("missing:{}".format(source.name))
    target.parent.mkdir(parents=True, exist_ok=True)
    image = sitk.ReadImage(str(source))
    mask = sitk.OtsuThreshold(image, 0, 1, 200)
    volume = sitk.Cast(image, sitk.sitkFloat32)
    corrector = sitk.N4BiasFieldCorrectionImageFilter()
    sitk.WriteImage(corrector.Execute(volume, mask), str(target))
    return target


def _affine_and_header(path: str | Path):
    import nibabel as nib
    import numpy as np

    image = nib.load(str(path))
    affine = image.affine.copy()
    if affine.shape != (4, 4):
        if affine.shape == (3, 4):
            fixed = np.eye(4)
            fixed[:3, :] = affine
            affine = fixed
        elif affine.shape == (4, 3):
            fixed = np.eye(4)
            fixed[:, :3] = affine
            affine = fixed
    return affine, image.header


def _binary_mask(path: str | Path):
    import nibabel as nib
    import numpy as np

    image = nib.load(str(path))
    data = image.get_fdata()
    # The experiment keeps a trailing singleton slice in MLO NIfTI contours.
    # Preserve it so paired masks have the same shape and the saved product
    # keeps the source image's dimensions.
    return (data > 0.5).astype(np.float32)


def _save_mask(array, affine, header, target: Path, dtype) -> Path:
    import nibabel as nib
    import numpy as np

    if dtype == np.float32:
        array = np.round(array, 4).astype(dtype)
    else:
        array = array.astype(dtype)
    target.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(array, affine, header), str(target))
    return target


def create_dce_decay(mask_a: str | Path, mask_b: str | Path,
                     target: str | Path, sigma_base: float = 3.0) -> Path:
    """Reproduce ``create_decay_mask_adaptive`` and its float16 output."""
    import numpy as np
    from scipy.ndimage import distance_transform_edt

    mask1 = _binary_mask(mask_a)
    mask2 = _binary_mask(mask_b)
    if mask1.shape != mask2.shape:
        raise PreprocessingError("shape:DCE_GTV:DCE_GTVnd1")
    combined = np.logical_or(mask1, mask2).astype(np.float32)
    radius = np.sqrt(np.sum(combined) / np.pi)
    if radius < 1:
        sigma = max(1.0, sigma_base * 0.5)
    elif radius < 1.5:
        sigma = sigma_base
    else:
        sigma = min(10.0, sigma_base * 1.5)
    distance = distance_transform_edt(1 - combined)
    distance = np.clip(distance, 0, 10 * sigma)
    decay = np.exp(-(distance ** 2) / (2 * sigma ** 2))
    decay[combined == 1] = 1.0
    affine, header = _affine_and_header(mask_a)
    return _save_mask(np.clip(decay, 0, 1), affine, header,
                      Path(target), np.float16)


def create_mlo_decay(mask_a: str | Path, mask_b: str | Path,
                     target: str | Path, distance_factor: float = 3.0) -> Path:
    """Reproduce ``create_linear_decay_adaptive`` and its float32 output."""
    import numpy as np
    from scipy.ndimage import distance_transform_edt

    mask1 = _binary_mask(mask_a)
    mask2 = _binary_mask(mask_b)
    if mask1.shape != mask2.shape:
        raise PreprocessingError("shape:MLO_GTV:MLO_GTVnd1")
    combined = np.logical_or(mask1, mask2).astype(np.float32)
    radius = np.sqrt(np.sum(combined) / np.pi)
    maximum = min(max(5, radius * distance_factor), 100)
    distance = distance_transform_edt(1 - combined)
    decay = 1 - distance / maximum
    decay[combined == 1] = 1
    affine, header = _affine_and_header(mask_a)
    return _save_mask(np.clip(decay, 0, 1), affine, header,
                      Path(target), np.float32)


def prepare_case_inputs(case_root: str | Path, case_id: str,
                        progress: Progress | None = None,
                        output_root: str | Path | None = None) -> PreparedInputs:
    """Reuse existing products, deriving only the missing offline outputs.

    A raw DCE can produce the N4 input; paired GTV/GTVnd1 contours can produce
    DCE and MLO decay masks. The MLO image and contours are independent source
    modalities and cannot be synthesized from DCE without changing experiment
    semantics, so their absence is reported as an input requirement.
    """
    root = Path(case_root)
    output = Path(output_root) if output_root is not None else root
    found = find_source_inputs(root, case_id)
    mlo = find_mlo_image(root, case_id) or found.mlo
    prepared = PreparedInputs(
        dce_n4=found.dce_n4, dce_decay=found.dce_decay,
        mlo=mlo, mlo_decay=found.mlo_decay)
    generated: list[str] = []

    def report(code: str, detail: str):
        prepared.messages.append(code)
        if progress:
            progress("prepare:{}:{}".format(code, detail))

    if prepared.dce_n4 is None and found.dce_raw is not None:
        report("preprocess.n4.running", case_id)
        prepared.dce_n4 = n4_bias_correction(
            found.dce_raw,
            output / "{}_DCE_N4_generated.nii.gz".format(case_id))
        generated.append("DCE_N4")
        report("preprocess.n4.done", case_id)

    if prepared.dce_decay is None and \
            found.dce_gtv is not None and found.dce_gtvnd1 is not None:
        report("preprocess.dce_decay.running", case_id)
        prepared.dce_decay = create_dce_decay(
            found.dce_gtv, found.dce_gtvnd1,
            output / "{}_DCE_decay1_generated.nii.gz".format(case_id))
        generated.append("DCE_decay1")
        report("preprocess.dce_decay.done", case_id)

    if prepared.mlo_decay is None and \
            found.mlo_gtv is not None and found.mlo_gtvnd1 is not None:
        report("preprocess.mlo_decay.running", case_id)
        prepared.mlo_decay = create_mlo_decay(
            found.mlo_gtv, found.mlo_gtvnd1,
            output / "MG" / "{}_MLO_decay1_generated.nii.gz".format(case_id))
        generated.append("MLO_decay1")
        report("preprocess.mlo_decay.done", case_id)

    prepared.generated = tuple(generated)
    return prepared


def preparing_status(prepared: PreparedInputs) -> str:
    """Stable validation code for the first still-required source input."""
    if prepared.dce_n4 is None:
        return "source.dce"
    if prepared.dce_decay is None:
        return "source.dce_gtv"
    if prepared.mlo is None:
        return "source.mlo"
    if prepared.mlo_decay is None:
        return "source.mlo_gtv"
    return ""
