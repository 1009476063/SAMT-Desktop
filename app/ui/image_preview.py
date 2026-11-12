"""Lightweight, read-only NIfTI slice preview for operator verification."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

if TYPE_CHECKING:
    import numpy as np


class ImagePreviewError(ValueError):
    """Raised when a selected file cannot be rendered as a preview."""


def _windowed_gray(plane: Any) -> Any:
    import numpy as np

    values = np.asarray(plane, dtype=np.float32)
    finite = values[np.isfinite(values)]
    if not finite.size:
        return np.zeros(values.shape, dtype=np.uint8)
    low, high = np.percentile(finite, (1, 99))
    if high <= low:
        high = low + 1
    scaled = np.clip((values - low) * 255 / (high - low), 0, 255)
    return scaled.astype(np.uint8)


def read_middle_slice(path: str | Path) -> tuple[Any, tuple[int, ...]]:
    """Read one NIfTI volume with SimpleITK and return its middle axial slice."""
    source = Path(path)
    if not source.is_file():
        raise ImagePreviewError("file-not-found")
    import SimpleITK as sitk
    import numpy as np

    try:
        image = sitk.ReadImage(str(source))
        volume = sitk.GetArrayFromImage(image)
    except Exception as exc:
        raise ImagePreviewError(str(exc)) from exc
    volume = np.asarray(volume)
    if volume.ndim == 2:
        plane = volume
    elif volume.ndim >= 3:
        plane = volume[volume.shape[0] // 2]
    else:
        raise ImagePreviewError("unsupported-dimensions")
    return _windowed_gray(plane), volume.shape


def preview_pixmap(path: str | Path, target_width: int = 420) -> tuple[QPixmap, str]:
    """Return a scaled grayscale pixmap and a short shape descriptor."""
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        raise ImagePreviewError("qt-application-required")
    gray, shape = read_middle_slice(path)
    height, width = gray.shape
    image = QImage(gray.tobytes(), width, height, width,
                   QImage.Format_Grayscale8).copy()
    pixmap = QPixmap.fromImage(image).scaledToWidth(
        max(1, target_width), Qt.SmoothTransformation)
    return pixmap, " × ".join(str(value) for value in shape)
