"""Read-only three-plane viewer for experiment NIfTI inputs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSlider,
    QVBoxLayout, QWidget,
)

from ui.image_preview import ImagePreviewError, _windowed_gray
from ui.theme import COLORS


ORIENTATIONS = ("axial", "coronal", "sagittal")
INPUT_LABEL_KEYS = {
    "DCE_N4": "inputs.dce_n4",
    "DCE_decay1": "inputs.dce_decay1",
    "MLO": "inputs.mlo",
    "MLO_decay1": "inputs.mlo_decay1",
    "dce_n4": "inputs.dce_n4",
    "dce_decay": "inputs.dce_decay1",
    "mlo": "inputs.mlo",
    "mlo_decay": "inputs.mlo_decay1",
}


def input_display_name(i18n, name: str) -> str:
    key = INPUT_LABEL_KEYS.get(name, "inputs." + name)
    return i18n.tr(key, fallback=name)


class ImageVolumeViewer(QDialog):
    """Browse all planes and slices of one or more selected NIfTI inputs."""

    def __init__(self, i18n, sources: dict[str, str | Path],
                 initial_key: str | None = None, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.sources = {
            str(name): Path(path) for name, path in sources.items()
            if path and Path(path).is_file()
        }
        if not self.sources:
            raise ImagePreviewError("file-not-found")
        self.volume_shape: tuple[int, ...] = ()
        self._volume: Any = None
        self._orientation = "axial"
        self._slice_index = 0
        self._zoom = 1.0
        self._window_cache: dict[tuple[str, int], QPixmap] = {}
        self.setModal(True)
        self.setMinimumSize(820, 620)
        self.resize(1080, 760)
        self._build_ui()
        requested = initial_key if initial_key in self.sources \
            else next(iter(self.sources))
        self.source_combo.blockSignals(True)
        self.source_combo.setCurrentIndex(
            self.source_combo.findData(requested))
        self.source_combo.blockSignals(False)
        self._load_source(requested)

    def _tr(self, key: str, **kwargs) -> str:
        return self.i18n.tr(key, **kwargs)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        heading = QHBoxLayout()
        title = QLabel(self._tr("viewer.title"))
        title.setProperty("role", "section")
        heading.addWidget(title, 1)
        self.close_btn = QPushButton(self._tr("common.close"))
        self.close_btn.clicked.connect(self.accept)
        heading.addWidget(self.close_btn)
        root.addLayout(heading)

        controls = QHBoxLayout()
        self.source_combo = QComboBox()
        for name in self.sources:
            self.source_combo.addItem(
                input_display_name(self.i18n, name), name)
        self.source_combo.currentIndexChanged.connect(
            self._on_source_changed)
        controls.addWidget(self.source_combo, 1)
        self.orientation_combo = QComboBox()
        for name in ORIENTATIONS:
            self.orientation_combo.addItem(
                self._tr("viewer.plane." + name), name)
        self.orientation_combo.currentIndexChanged.connect(
            self._on_orientation_changed)
        controls.addWidget(self.orientation_combo)
        self.fit_btn = QPushButton(self._tr("viewer.fit"))
        self.fit_btn.clicked.connect(self.fit_to_window)
        controls.addWidget(self.fit_btn)
        root.addLayout(controls)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 440)
        self.image_label.setStyleSheet(
            "background: {}; border: 1px solid {}; border-radius: 5px;"
            .format(COLORS["tree"], COLORS["border"]))
        root.addWidget(self.image_label, 1)

        slice_controls = QHBoxLayout()
        self.previous_btn = QPushButton("−")
        self.previous_btn.setToolTip(self._tr("viewer.previous"))
        self.previous_btn.clicked.connect(lambda: self.step_slice(-1))
        slice_controls.addWidget(self.previous_btn)
        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.valueChanged.connect(self._on_slice_changed)
        slice_controls.addWidget(self.slice_slider, 1)
        self.next_btn = QPushButton("+")
        self.next_btn.setToolTip(self._tr("viewer.next"))
        self.next_btn.clicked.connect(lambda: self.step_slice(1))
        slice_controls.addWidget(self.next_btn)
        root.addLayout(slice_controls)
        self.slice_label = QLabel()
        self.slice_label.setProperty("role", "caption")
        root.addWidget(self.slice_label)

    def _load_source(self, name: str):
        import SimpleITK as sitk
        import numpy as np

        path = self.sources[name]
        try:
            image = sitk.ReadImage(str(path))
            volume = np.asarray(sitk.GetArrayFromImage(image))
        except Exception as exc:
            raise ImagePreviewError(str(exc)) from exc
        if volume.ndim not in (2, 3) or any(dim <= 0 for dim in volume.shape):
            raise ImagePreviewError("unsupported-dimensions")
        self._volume = volume
        self.volume_shape = tuple(int(value) for value in volume.shape)
        self._window_cache = {}
        self.set_orientation("axial")

    def _sources_for_plane(self):
        if self._volume is None:
            raise ImagePreviewError("no-volume")
        if self._volume.ndim == 2:
            return self._volume
        return {
            "axial": self._volume,
            "coronal": self._volume.transpose(1, 0, 2),
            "sagittal": self._volume.transpose(2, 0, 1),
        }[self._orientation]

    def current_plane(self):
        volume = self._sources_for_plane()
        if self._volume.ndim == 2:
            return volume
        return volume[self._slice_index]

    def slice_index(self) -> int:
        return int(self._slice_index)

    def set_orientation(self, orientation: str):
        if orientation not in ORIENTATIONS:
            raise ValueError("unknown-orientation")
        self._orientation = orientation
        index = self.orientation_combo.findData(orientation)
        if index >= 0 and self.orientation_combo.currentIndex() != index:
            self.orientation_combo.blockSignals(True)
            self.orientation_combo.setCurrentIndex(index)
            self.orientation_combo.blockSignals(False)
        maximum = 0 if self._volume is None or self._volume.ndim == 2 \
            else self._sources_for_plane().shape[0] - 1
        self._slice_index = min(max(0, self._slice_index), maximum)
        self.slice_slider.blockSignals(True)
        self.slice_slider.setRange(0, maximum)
        self.slice_slider.setValue(self._slice_index)
        self.slice_slider.blockSignals(False)
        self._render()

    def step_slice(self, amount: int):
        self.slice_slider.setValue(
            min(max(self.slice_slider.value() + amount,
                    self.slice_slider.minimum()),
                self.slice_slider.maximum()))

    def fit_to_window(self):
        self._zoom = 1.0
        self._render()

    def _on_source_changed(self, _index: int):
        if self.source_combo.currentData():
            self._load_source(self.source_combo.currentData())

    def _on_orientation_changed(self, _index: int):
        orientation = self.orientation_combo.currentData()
        if orientation:
            self.set_orientation(orientation)

    def _on_slice_changed(self, value: int):
        self._slice_index = int(value)
        self._render()

    def _render(self):
        if self._volume is None:
            return
        plane = self.current_plane()
        key = (self._orientation, self._slice_index)
        pixmap = self._window_cache.get(key)
        if pixmap is None:
            gray = _windowed_gray(plane)
            height, width = gray.shape
            image = QImage(gray.tobytes(), width, height, width,
                           QImage.Format_Grayscale8).copy()
            pixmap = QPixmap.fromImage(image)
            self._window_cache[key] = pixmap
        target = self.image_label.size()
        scaled = pixmap.scaled(
            max(1, target.width() - 16), max(1, target.height() - 16),
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        maximum = self.slice_slider.maximum()
        self.slice_label.setText(self._tr(
            "viewer.slice", current=self._slice_index + 1,
            total=maximum + 1,
            shape=" × ".join(str(value) for value in self.volume_shape),
            plane=self._tr("viewer.plane." + self._orientation)))

    def resizeEvent(self, event):  # noqa: D102, N802
        super().resizeEvent(event)
        self._render()
