"""SAMT Desktop main window: a focused, bilingual research workbench."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QThread, QThreadPool, QTimer, Signal, Slot
from PySide6.QtGui import QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox,
    QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QStackedWidget, QTableWidget,
    QTextBrowser, QToolButton,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

APP_DIR = Path(__file__).resolve().parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from i18n import I18n  # noqa: E402
from settings import Settings  # noqa: E402
from core.experiment_contract import (  # noqa: E402
    CLINICAL_COLUMNS, PATHOLOGY_COLUMNS, experiment_tree_description,
    localized_problem,
)
from core.contract_catalog import (  # noqa: E402
    catalog_cases, resolve_experiment_root,
)
from core.clinical_table import (  # noqa: E402
    clinical_coverage, localized_error,
)
from ui.clinical_import_dialog import ClinicalImportDialog  # noqa: E402
from ui.image_preview import ImagePreviewError, preview_pixmap  # noqa: E402
from ui.theme import COLORS  # noqa: E402

if TYPE_CHECKING:
    from core.engine import PatientCase


# The expanded consent requires one fresh acceptance on upgrade.
DISCLAIMER_VERSION = "1.3.0"


def _language_icon() -> QIcon:
    """Draw a compact globe glyph without external icon assets."""
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(COLORS["accent_hover"])
    painter.drawEllipse(4, 4, 24, 24)
    painter.drawLine(4, 16, 28, 16)
    painter.drawLine(16, 4, 16, 28)
    painter.drawArc(9, 4, 14, 24, 65 * 16, 230 * 16)
    painter.end()
    return QIcon(pixmap)


def has_current_consent(settings: Settings) -> bool:
    """True when the current declaration was explicitly accepted before."""
    return bool(settings.data.get("disclaimer_accepted")) and \
        settings.data.get("remember_consent", True) and \
        settings.data.get("accepted_disclaimer_version") == DISCLAIMER_VERSION


def _bundled_models_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "models").is_dir():
        return Path(meipass) / "models"
    # macOS BUNDLE() places PyInstaller data under Contents/Resources while
    # the launcher lives in Contents/MacOS. Keep that layout discoverable.
    resources = APP_DIR.parent / "Resources"
    if resources.name == "Resources" and (resources / "models").is_dir():
        return resources / "models"
    return APP_DIR / "models"


BUNDLED_MODELS = _bundled_models_dir()


def _panel(parent=None) -> QFrame:
    frame = QFrame(parent)
    frame.setProperty("role", "panel")
    return frame


def _section_label(text: str, parent=None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("role", "section")
    return label


def _caption(text: str, parent=None) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("role", "caption")
    label.setWordWrap(True)
    return label


def _divider(parent=None) -> QFrame:
    line = QFrame(parent)
    line.setFrameShape(QFrame.HLine)
    line.setProperty("role", "divider")
    return line


class ResearchUseGate(QDialog):
    """Standalone consent gate shown before any main window exists."""

    def __init__(self, i18n: I18n, settings: Settings, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.settings = settings
        self.setWindowTitle(i18n.tr("disclaimer.title"))
        self.setModal(True)
        self.setMinimumSize(720, 620)
        self.resize(800, 700)
        self.setWindowFlags(
            (self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            | Qt.Dialog | Qt.WindowStaysOnTopHint
        )
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 24)
        root.setSpacing(12)
        header = QFrame()
        header.setProperty("role", "panel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 16, 14)
        mark = QLabel("S")
        mark.setFixedSize(42, 42)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            "background: {}; color: white; border-radius: 6px; "
            "font-size: 19pt; font-weight: 600;".format(COLORS["accent"]))
        header_layout.addWidget(mark)
        copy = QVBoxLayout()
        copy.setSpacing(2)
        self.title_label = _section_label(self.i18n.tr("disclaimer.title"))
        self.subtitle_label = _caption(
            self.i18n.tr("disclaimer.subtitle"))
        copy.addWidget(self.title_label)
        copy.addWidget(self.subtitle_label)
        header_layout.addLayout(copy, 1)
        self.language_button = QToolButton()
        self.language_button.setIcon(_language_icon())
        self.language_button.setIconSize(QSize(20, 20))
        self.language_button.setToolTip(
            self.i18n.tr("common.language_zh")
            if self.i18n.lang == "en-US" else
            self.i18n.tr("common.language_en"))
        self.language_button.clicked.connect(self._toggle_language)
        header_layout.addWidget(self.language_button)
        root.addWidget(header)

        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(False)
        self.body.setReadOnly(True)
        self.body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        root.addWidget(self.body, 1)
        self.hide_reminder = QCheckBox(
            self.i18n.tr("disclaimer.hide_reminder"))
        self.hide_reminder.setChecked(True)
        root.addWidget(self.hide_reminder)
        self.checkbox = QCheckBox(self.i18n.tr("disclaimer.accept"))
        root.addWidget(self.checkbox)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton(self.i18n.tr("disclaimer.cancel"))
        self.cancel_btn.clicked.connect(self.reject)
        self.enter_btn = QPushButton(self.i18n.tr("disclaimer.enter"))
        self.enter_btn.setProperty("role", "primary")
        self.enter_btn.setEnabled(False)
        self.enter_btn.setDefault(True)
        self.enter_btn.clicked.connect(self.accept)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.enter_btn)
        root.addLayout(buttons)
        self.checkbox.toggled.connect(self._sync_actions)
        self.hide_reminder.toggled.connect(
            lambda checked: self.settings.data.update(
                remember_consent=checked))
        self._retranslate()

    def _consent_html(self) -> str:
        sections = []
        for index in range(1, 6):
            title = self.i18n.tr(f"disclaimer.section{index}")
            body = self.i18n.tr(f"disclaimer.section{index}_body")
            sections.append(
                "<h3 style='margin:12px 0 4px 0;'>{}</h3>"
                "<p style='margin:0 0 8px 0; line-height:150%;'>{}</p>"
                .format(title, body))
        return "".join(sections)

    def _retranslate(self):
        self.setWindowTitle(self.i18n.tr("disclaimer.title"))
        self.title_label.setText(self.i18n.tr("disclaimer.title"))
        self.subtitle_label.setText(self.i18n.tr("disclaimer.subtitle"))
        self.body.setHtml(self._consent_html())
        self.hide_reminder.setText(self.i18n.tr("disclaimer.hide_reminder"))
        self.checkbox.setText(self.i18n.tr("disclaimer.accept"))
        self.cancel_btn.setText(self.i18n.tr("disclaimer.cancel"))
        self.enter_btn.setText(self.i18n.tr("disclaimer.enter"))
        target = "zh-CN" if self.i18n.lang == "en-US" else "en-US"
        self.language_button.setToolTip(
            self.i18n.tr("common.switch_language"))

    def _toggle_language(self):
        target = "zh-CN" if self.i18n.lang == "en-US" else "en-US"
        self.i18n.set_language(target)
        self.settings.data["language"] = target
        self.settings.save()
        self._retranslate()

    def _sync_actions(self):
        self.enter_btn.setEnabled(self.checkbox.isChecked())

    def showEvent(self, event):  # noqa: D102, N802
        super().showEvent(event)
        self._force_foreground()
        if sys.platform == "win32":
            # Windows may suppress a foreground request from a background
            # process. Retry after the native window has been created.
            QTimer.singleShot(120, self._force_foreground)
            QTimer.singleShot(650, self._force_foreground)

    def _force_foreground(self):
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.checkbox.setFocus()

    def accept(self):  # noqa: D102
        self.settings.data["disclaimer_accepted"] = True
        self.settings.data["remember_consent"] = \
            bool(self.hide_reminder.isChecked())
        self.settings.data["accepted_disclaimer_version"] = DISCLAIMER_VERSION
        self.settings.data["language"] = self.i18n.lang
        self.settings.save()
        super().accept()


def _clinical_columns() -> list[str]:
    return list(CLINICAL_COLUMNS) + list(PATHOLOGY_COLUMNS)


class EngineInitThread(QThread):
    checkpoint_progress = Signal(int, int)
    engine_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, models_dir: Path, device: str, low_memory: bool,
                 parent=None):
        # No Qt parent: the main window can close while a 1.7 GiB checkpoint
        # load is still running. It owns this thread and waits for it instead.
        super().__init__()
        self.models_dir = models_dir
        self.device = device
        self.low_memory = low_memory
        self.engine_result = None
        self.error = ""

    def run(self):
        import torch
        from core.engine import InferenceEngine

        cpu_count = QThreadPool.globalInstance().maxThreadCount()
        torch.set_num_threads(max(1, min(cpu_count, 16)))

        def report(text: str):
            if text.startswith("checkpoint:"):
                _, done, total = text.split(":")
                self.checkpoint_progress.emit(int(done), int(total))
            elif text == "fallback:cpu":
                self.checkpoint_progress.emit(-1, 0)

        try:
            engine = InferenceEngine(
                self.models_dir, device=self.device, on_status=report,
                retain_checkpoints=not self.low_memory)
            if engine.checkpoint_count == 0:
                raise RuntimeError("error.no_checkpoints")
            engine.warm_up()
            self.engine_result = engine
            self.engine_ready.emit(engine)
        except Exception as exc:  # pragma: no cover - surfaced by UI
            self.error = str(exc)
            self.failed.emit(str(exc))


class InferThread(QThread):
    progress_text = Signal(str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, engine, cases, parent=None):
        super().__init__()
        self.engine = engine
        self.cases = cases

    def run(self):
        try:
            self.progress_text.emit("stage")
            self.progress_text.emit("preprocess")
            results = self.engine.infer_staged_batch(
                self.cases, progress=self.progress_text.emit)
            self.finished_ok.emit(results)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.i18n = I18n(self.settings.data.get("language", ""))
        self.engine = None
        self.batch_cases: list = []
        self.batch_results = []
        self.form_edits: dict[str, QWidget] = {}
        self._translations: list[tuple[QWidget, str, str]] = []
        self._dynamic_text: dict[QWidget, tuple[str, dict]] = {}
        self._field_labels: dict[str, str] = {}
        self._case_rows: list = []
        self._batch_result_rows: dict[str, dict[int, str]] = {}
        self._last_df = None
        self._last_single_result = None
        self._active_thread = None
        self._init_thread = None
        self._closing = False
        self._busy = False
        self._build_ui()
        self._connect_shortcuts()
        self._prepare_engine()

    # ------------------------------------------------------------ UI setup
    def _build_ui(self):
        self.setWindowTitle(self.i18n.tr("app.short"))
        self.setMinimumSize(1080, 720)
        self.resize(1360, 860)
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_rail())
        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_single_page())
        self.pages.addWidget(self._build_batch_page())
        self.pages.addWidget(self._build_settings_page())
        self.pages.addWidget(self._build_about_page())
        body.addWidget(self.pages, 1)
        root.addLayout(body, 1)
        self.setCentralWidget(central)

        self.status_bar = self.statusBar()
        self.status_label = self._tracked(QLabel(), "status.ready")
        self.model_label = QLabel("10 / 10")
        self.backend_label = QLabel("CPU")
        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.model_label)
        self.status_bar.addPermanentWidget(QLabel("  |  "))
        self.status_bar.addPermanentWidget(self.backend_label)
        self._set_disabled_while_preparing()

    def _tracked(self, widget: QWidget, key: str, method: str = "setText"):
        self._translations.append((widget, key, method))
        getattr(widget, method)(self.i18n.tr(key))
        return widget

    def _set_status(self, widget: QWidget, key: str, **kwargs):
        """Remember a runtime message so language changes re-render it."""
        self._dynamic_text[widget] = (key, kwargs)
        widget.setText(self.i18n.tr(key, **kwargs))

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setProperty("role", "header")
        header.setFixedHeight(76)
        row = QHBoxLayout(header)
        row.setContentsMargins(24, 12, 24, 12)
        row.setSpacing(14)
        mark = QLabel("S")
        mark.setFixedSize(42, 42)
        mark.setAlignment(Qt.AlignCenter)
        mark.setStyleSheet(
            "background: {}; color: white; border-radius: 6px; "
            "font-size: 19pt; font-weight: 600;".format(COLORS["accent"]))
        row.addWidget(mark)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        title = self._tracked(QLabel(), "app.short")
        title.setProperty("role", "title")
        titles.addWidget(title)
        titles.addWidget(self._tracked(_caption(""), "app.subtitle"))
        row.addLayout(titles, 1)
        scope = self._tracked(QLabel(), "common.research")
        scope.setStyleSheet(
            "color: {}; background: {}; border: 1px solid {}; "
            "border-radius: 5px; padding: 5px 10px;".format(
                COLORS["accent_hover"], COLORS["accent_soft"], COLORS["accent"]))
        row.addWidget(scope)
        self.language_toggle = QPushButton(
            _language_icon(), "")
        self.language_toggle.setIconSize(QSize(20, 20))
        self.language_toggle.setFixedWidth(38)
        self.language_toggle.setToolTip(
            self.i18n.tr("common.switch_language"))
        self.language_toggle.clicked.connect(self._quick_toggle_language)
        row.addWidget(self.language_toggle)
        return header

    def _build_rail(self) -> QFrame:
        rail = QFrame()
        rail.setProperty("role", "rail")
        rail.setFixedWidth(214)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(14, 20, 14, 18)
        layout.setSpacing(6)
        layout.addWidget(self._tracked(_caption(""), "nav.section"))
        layout.addSpacing(8)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, key in enumerate(
                ("nav.single", "nav.batch", "nav.settings", "nav.about")):
            button = self._tracked(QPushButton(), key)
            button.setProperty("role", "nav")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _, i=index: self._navigate(i))
            self.nav_group.addButton(button, index)
            layout.addWidget(button)
        self.nav_group.button(0).setChecked(True)
        layout.addStretch(1)
        layout.addWidget(_divider())
        self.model_status_label = self._tracked(
            _caption(""), "status.preparing")
        layout.addWidget(self.model_status_label)
        self.load_progress = QProgressBar()
        self.load_progress.setRange(0, 10)
        self.load_progress.setValue(0)
        self.load_progress.setFormat("%v / %m")
        layout.addWidget(self.load_progress)
        self.fingerprint_label = _caption("")
        layout.addWidget(self.fingerprint_label)
        return rail

    def _navigate(self, index: int):
        self.pages.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)

    @staticmethod
    def _page_scroll(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(widget)
        return scroll

    def _page_heading(self, title_key: str, subtitle_key: str) -> QVBoxLayout:
        block = QVBoxLayout()
        block.setSpacing(4)
        title = self._tracked(QLabel(), title_key)
        title.setProperty("role", "title")
        block.addWidget(title)
        block.addWidget(self._tracked(_caption(""), subtitle_key))
        return block

    # --------------------------------------------------------- single page
    def _build_single_page(self) -> QScrollArea:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(12)
        root.addLayout(self._page_heading("single.title", "single.subtitle"))
        top = QGridLayout()
        top.setSpacing(12)
        top.addWidget(self._build_single_input_panel(), 0, 0)
        top.addWidget(self._build_single_workspace_panel(), 0, 1)
        top.setColumnStretch(0, 2)
        top.setColumnStretch(1, 3)
        root.addLayout(top, 3)
        root.addWidget(self._build_fold_panel(), 1)
        return self._page_scroll(page)

    def _build_single_input_panel(self) -> QFrame:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(self._tracked(_section_label(""), "single.images"))
        layout.addWidget(self._tracked(_caption(""), "single.images_hint"))
        self.file_edits: dict[str, QLineEdit] = {}
        files_form = QFormLayout()
        files_form.setLabelAlignment(Qt.AlignRight)
        files_form.setSpacing(8)
        for key, label_key in [
            ("dce_n4", "single.dce_n4"),
            ("dce_decay", "single.dce_decay"),
            ("mlo", "single.mlo"),
            ("mlo_decay", "single.mlo_decay"),
        ]:
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setReadOnly(True)
            edit.setPlaceholderText(self.i18n.tr("common.missing"))
            browse = self._tracked(QPushButton(), "common.browse")
            browse.setFixedWidth(86)
            browse.clicked.connect(lambda _, e=edit: self._pick_nifti(e))
            row.addWidget(edit, 1)
            row.addWidget(browse)
            files_form.addRow(self._tracked(QLabel(), label_key), row)
            self.file_edits[key] = edit
        layout.addLayout(files_form)
        layout.addWidget(_divider())
        case_row = QHBoxLayout()
        case_row.addWidget(self._tracked(QLabel(), "single.case_id"))
        self.case_id_edit = QLineEdit()
        self.case_id_edit.setPlaceholderText("case1")
        case_row.addWidget(self.case_id_edit, 1)
        layout.addLayout(case_row)
        layout.addWidget(self._tracked(
            _caption(""), "single.case_id_hint"))
        table_row = QHBoxLayout()
        self.import_table_btn = self._tracked(
            QPushButton(), "single.import_table")
        self.import_table_btn.clicked.connect(self.import_clinical_table)
        self.import_table_status = _caption("")
        table_row.addWidget(self.import_table_btn)
        table_row.addWidget(self.import_table_status, 1)
        layout.addLayout(table_row)
        variables = QHBoxLayout()
        variables.setSpacing(18)
        variables.addWidget(self._build_form_group(
            "single.clinical", CLINICAL_COLUMNS), 1)
        variables.addWidget(self._build_form_group(
            "single.pathology", PATHOLOGY_COLUMNS), 1)
        layout.addLayout(variables, 1)
        self.coverage_label = _caption("")
        layout.addWidget(self.coverage_label)
        self.coverage_bar = QProgressBar()
        self.coverage_bar.setRange(0, 100)
        self.coverage_bar.setValue(0)
        self.coverage_bar.setTextVisible(True)
        self.coverage_bar.setFormat("%v%")
        layout.addWidget(self.coverage_bar)
        for widget in self.form_edits.values():
            if isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._refresh_coverage)
            else:
                widget.textChanged.connect(self._refresh_coverage)
        self._refresh_coverage()
        layout.addWidget(self._tracked(_caption(""), "single.form_hint"))
        action = QHBoxLayout()
        action.addStretch(1)
        self.single_run_btn = self._tracked(QPushButton(), "single.run")
        self.single_run_btn.setProperty("role", "primary")
        self.single_run_btn.setMinimumWidth(180)
        self.single_run_btn.clicked.connect(self.run_single)
        action.addWidget(self.single_run_btn)
        layout.addLayout(action)
        return panel

    def _build_form_group(self, title_key: str,
                          columns: list[str]) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        section = self._tracked(_section_label(""), title_key)
        layout.addWidget(section)
        form = QFormLayout()
        form.setSpacing(7)
        form.setLabelAlignment(Qt.AlignRight)
        for column in columns:
            label_key, values = self._field_spec(column)
            if values:
                widget = QComboBox()
                for value in values:
                    widget.addItem(self._value_text(value), value)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText("0")
            widget.setToolTip(column)
            widget.setAccessibleName(self.i18n.tr(label_key))
            label = self._tracked(QLabel(), label_key)
            self._field_labels[column] = label_key
            form.addRow(label, widget)
            self.form_edits[column] = widget
        layout.addLayout(form)
        layout.addStretch(1)
        return box

    def _value_text(self, value: str) -> str:
        translatable = ("Unifocal", "Multifocal", "Multicentric", "Yes", "No",
                        "Absent", "Present", "Other")
        return self.i18n.tr("values." + value) \
            if value in translatable else value

    @staticmethod
    def _field_spec(column: str) -> tuple[str, list[str] | None]:
        specs = {
            "Laterality ": ("fields.Laterality", ["Left", "Right"]),
            "Multifocality（Tumor number）": (
                "fields.Multifocality",
                ["Unifocal", "Multifocal", "Multicentric"]),
            "Location(nine)": (
                "fields.Location",
                ["UQ", "OQ", "LQ", "IQ", "UOQ", "LOQ", "LIQ", "UIQ", "CenP"]),
            "cT": ("fields.cT", ["T0", "T1", "T2", "T3", "T4"]),
            "Calcification": ("fields.Calcification", ["Yes", "No"]),
            "Breast density ": ("fields.Breast_density", ["A", "B", "C", "D"]),
            "Age": ("fields.Age", None),
            "Tumor size MRI ": ("fields.Tumor_size", None),
            "max diameter with lowest layer of ALN": (
                "fields.ALN_diameter", None),
            "Histological type  (needle biopsy)": (
                "fields.Histological_type",
                ["Invasive ductal carcinoma", "Invasive lobular carcinoma",
                 "Invasive carcinoma", "Invasive micropapillary carcinoma",
                 "Ductal carcinoma in situ", "Other"]),
            "Histological grade ": (
                "fields.Histological_grade", ["I", "II", "III"]),
            "ER": ("fields.ER", ["+", "-"]),
            "PR": ("fields.PR", ["+", "-"]),
            "HER2": ("fields.HER2", ["+", "-"]),
            "LVI": ("fields.LVI", ["Absent", "Present"]),
            "Ki67": ("fields.Ki67", ["-", "<20%", "+", ">=20%"]),
            "SLN-positive": ("fields.SLN_positive", None),
            "total SLN": ("fields.total_SLN", None),
            "Positive_Total_SLN_ratio": ("fields.SLN_ratio", None),
        }
        return specs.get(column, ("common.optional", None))

    def _build_single_workspace_panel(self) -> QFrame:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(self._tracked(
            _section_label(""), "preview.title"))
        self.preview_image = self._tracked(
            QLabel(), "common.preview_empty")
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setMinimumHeight(260)
        self.preview_image.setWordWrap(True)
        self.preview_image.setStyleSheet(
            "background: {}; border: 1px solid {}; border-radius: 5px;"
            .format(COLORS["surface_alt"], COLORS["border"]))
        layout.addWidget(self.preview_image, 1)
        preview_row = QHBoxLayout()
        self.preview_selector = self._tracked(
            QPushButton(), "common.preview")
        self.preview_selector.clicked.connect(self._show_image_preview)
        self.preview_shape = _caption("")
        preview_row.addWidget(self.preview_selector)
        preview_row.addWidget(self.preview_shape, 1)
        layout.addLayout(preview_row)
        layout.addWidget(_divider())
        layout.addWidget(self._tracked(
            _section_label(""), "single.result"))
        self.result_empty = self._tracked(
            QLabel(), "single.empty_result")
        self.result_empty.setWordWrap(True)
        self.result_empty.setProperty("role", "caption")
        layout.addWidget(self.result_empty)
        self.result_body = QWidget()
        result_layout = QVBoxLayout(self.result_body)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(10)
        result_layout.addWidget(self._tracked(
            _caption(""), "single.prob_pos"))
        self.positive_prob = QLabel("--")
        self.positive_prob.setProperty("role", "probability")
        result_layout.addWidget(self.positive_prob)
        self.positive_bar = self._probability_bar(COLORS["positive"])
        result_layout.addWidget(self.positive_bar)
        result_layout.addStretch(1)
        neg_row = QHBoxLayout()
        neg_row.addWidget(self._tracked(_caption(""), "single.prob_neg"))
        self.negative_prob = QLabel("--")
        self.negative_prob.setStyleSheet(
            "font-size: 15pt; font-weight: 600; color: {};".format(
                COLORS["negative"]))
        neg_row.addWidget(self.negative_prob, 1, Qt.AlignRight)
        result_layout.addLayout(neg_row)
        self.negative_bar = self._probability_bar(COLORS["negative"])
        result_layout.addWidget(self.negative_bar)
        pred_row = QHBoxLayout()
        pred_row.addWidget(self._tracked(QLabel(), "single.prediction"))
        self.prediction_label = QLabel("--")
        self.prediction_label.setStyleSheet("font-weight: 600; font-size: 12pt;")
        pred_row.addWidget(self.prediction_label, 1, Qt.AlignRight)
        result_layout.addLayout(pred_row)
        self.result_body.setVisible(False)
        layout.addWidget(self.result_body, 1)
        self.single_progress = QProgressBar()
        self.single_progress.setRange(0, 10)
        self.single_progress.setValue(0)
        self.single_progress.setVisible(False)
        layout.addWidget(self.single_progress)
        self.run_log = QLabel("")
        self.run_log.setWordWrap(True)
        self.run_log.setProperty("role", "caption")
        layout.addWidget(self.run_log)
        actions = QHBoxLayout()
        actions.addStretch(1)
        self.single_export_btn = self._tracked(QPushButton(), "single.export")
        self.single_export_btn.setEnabled(False)
        self.single_export_btn.clicked.connect(self.export_single)
        actions.addWidget(self.single_export_btn)
        layout.addLayout(actions)
        return panel

    def _show_image_preview(self):
        for edit in self.file_edits.values():
            path = edit.text().strip()
            if path and Path(path).is_file():
                break
        else:
            self.preview_image.setText(self.i18n.tr("common.preview_empty"))
            self.preview_shape.setText("")
            return
        try:
            pixmap, shape = preview_pixmap(
                path, max(320, self.preview_image.width() - 20))
        except (ImagePreviewError, OSError, ValueError) as exc:
            self.preview_image.setText(self.i18n.tr(
                "common.preview_failed", error=str(exc)))
            self.preview_shape.setText("")
            return
        self.preview_image.setPixmap(pixmap)
        self.preview_shape.setText(self.i18n.tr(
            "single.preview_shape", shape=shape))

    @staticmethod
    def _probability_bar(color: str) -> QProgressBar:
        bar = QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet(
            "QProgressBar {{ border: 0px; background: {}; border-radius: 4px; }}"
            "QProgressBar::chunk {{ background: {}; border-radius: 4px; }}".format(
                COLORS["disabled"], color))
        return bar

    def _build_fold_panel(self) -> QFrame:
        panel = _panel()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.addWidget(self._tracked(
            _section_label(""), "single.fold_table"))
        self.fold_table = QTableWidget(10, 3)
        self._set_table_headers(
            self.fold_table, ("single.fold", "single.probability_neg",
                              "single.probability_pos"))
        self.fold_table.verticalHeader().setVisible(False)
        self.fold_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.fold_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch)
        self.fold_table.setMaximumHeight(248)
        layout.addWidget(self.fold_table)
        return panel

    def _set_table_headers(self, table: QTableWidget, keys):
        table.setHorizontalHeaderLabels([self.i18n.tr(key) for key in keys])
        table.setProperty("header_keys", tuple(keys))

    # ---------------------------------------------------------- batch page
    def _build_batch_page(self) -> QScrollArea:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)
        root.addLayout(self._page_heading("batch.title", "batch.subtitle"))
        controls = QFrame()
        controls.setProperty("role", "panel")
        row = QHBoxLayout(controls)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(10)
        self.batch_dir_edit = QLineEdit(
            self.settings.data.get("last_data_dir", ""))
        self.batch_dir_edit.setPlaceholderText(self.i18n.tr("batch.dir_hint"))
        browse = self._tracked(QPushButton(), "common.browse")
        browse.clicked.connect(self._pick_data_dir)
        self.batch_scan_btn = self._tracked(QPushButton(), "batch.scan")
        self.batch_scan_btn.clicked.connect(self.scan_batch)
        self.batch_run_btn = self._tracked(QPushButton(), "batch.run")
        self.batch_run_btn.setProperty("role", "primary")
        self.batch_run_btn.clicked.connect(self.run_batch)
        self.batch_export_btn = self._tracked(QPushButton(), "batch.export")
        self.batch_export_btn.clicked.connect(self.export_batch)
        row.addWidget(self.batch_dir_edit, 1)
        row.addWidget(browse)
        row.addWidget(self.batch_scan_btn)
        row.addWidget(self.batch_run_btn)
        row.addWidget(self.batch_export_btn)
        root.addWidget(controls)
        self.structure_label = _caption("")
        root.addWidget(self.structure_label)
        self.batch_table = QTableWidget(0, 8)
        self._set_table_headers(self.batch_table, (
            "batch.column_case", "batch.column_label",
            "batch.column_coverage", "batch.column_status",
            "batch.column_neg", "batch.column_pos",
            "batch.column_pred", "common.files"))
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.batch_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setMinimumHeight(320)
        root.addWidget(self.batch_table, 1)
        progress_row = QHBoxLayout()
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 1)
        self.batch_progress.setValue(0)
        self.batch_status = self._tracked(_caption(""), "batch.empty")
        progress_row.addWidget(self.batch_progress, 1)
        progress_row.addWidget(self.batch_status, 2)
        root.addLayout(progress_row)
        return self._page_scroll(page)

    # ------------------------------------------------------- settings page
    def _build_settings_page(self) -> QScrollArea:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)
        root.addLayout(self._page_heading("settings.title", "settings.subtitle"))
        panel = _panel()
        panel.setMaximumWidth(760)
        form = QFormLayout(panel)
        form.setContentsMargins(22, 20, 22, 20)
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)
        self.language_combo = QComboBox()
        self.language_combo.addItem(self.i18n.tr("common.language_zh"),
                                    "zh-CN")
        self.language_combo.addItem(self.i18n.tr("common.language_en"),
                                    "en-US")
        self.language_combo.setCurrentIndex(
            0 if self.i18n.lang == "zh-CN" else 1)
        form.addRow(self._tracked(QLabel(), "settings.language"),
                    self.language_combo)
        form.addRow("", self._tracked(
            _caption(""), "settings.language_hint"))
        models_row = QHBoxLayout()
        self.models_edit = QLineEdit(
            self.settings.data.get("models_dir", "") or str(BUNDLED_MODELS))
        self.models_edit.setReadOnly(True)
        detect_btn = self._tracked(QPushButton(), "settings.detect")
        detect_btn.clicked.connect(self._choose_models_dir)
        models_row.addWidget(self.models_edit, 1)
        models_row.addWidget(detect_btn)
        form.addRow(self._tracked(QLabel(), "settings.models_dir"), models_row)
        self.device_combo = QComboBox()
        self.device_combo.addItem(
            "CPU · " + self.i18n.tr("common.reference"), "cpu")
        self.device_combo.addItem("CUDA", "cuda")
        self.device_combo.addItem("MPS", "mps")
        saved_device = self.settings.data.get("device", "cpu")
        index = self.device_combo.findData(saved_device)
        self.device_combo.setCurrentIndex(max(index, 0))
        form.addRow(self._tracked(QLabel(), "settings.backend"),
                    self.device_combo)
        form.addRow("", self._tracked(
            _caption(""), "settings.backend_hint"))
        self.low_memory_check = self._tracked(
            QCheckBox(), "settings.low_memory")
        self.low_memory_check.setChecked(
            bool(self.settings.data.get("low_memory", False)))
        form.addRow("", self.low_memory_check)
        apply_row = QHBoxLayout()
        apply_row.addStretch(1)
        self.apply_settings_btn = self._tracked(
            QPushButton(), "settings.apply")
        self.apply_settings_btn.setProperty("role", "primary")
        self.apply_settings_btn.clicked.connect(self.apply_settings)
        apply_row.addWidget(self.apply_settings_btn)
        form.addRow("", apply_row)
        self.models_status = _caption("")
        form.addRow("", self.models_status)
        root.addWidget(panel)
        root.addStretch(1)
        return self._page_scroll(page)

    # ----------------------------------------------------------- about page
    def _build_about_page(self) -> QScrollArea:
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(16)
        root.addLayout(self._page_heading("about.title", "about.subtitle"))
        grid = QGridLayout()
        grid.setSpacing(16)
        sections = [
            ("about.pipeline_title", "about.pipeline", 0, 0),
            ("about.ensemble_title", "about.ensemble", 0, 1),
            ("about.scope_title", "about.research_only", 1, 0),
            ("about.structure_title", "about.structure", 1, 1),
        ]
        for title_key, body_key, row, column in sections:
            panel = _panel()
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(20, 18, 20, 18)
            layout.setSpacing(8)
            layout.addWidget(self._tracked(_section_label(""), title_key))
            body = self._tracked(QLabel(), body_key)
            body.setWordWrap(True)
            layout.addWidget(body)
            layout.addStretch(1)
            grid.addWidget(panel, row, column)
        root.addLayout(grid, 1)
        self.version_label = _caption("")
        root.addWidget(self.version_label)
        self._refresh_version_label()
        return self._page_scroll(page)

    def _connect_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self,
                  activated=self._open_first_image)
        QShortcut(QKeySequence("Ctrl+Return"), self,
                  activated=self.run_single)
        QShortcut(QKeySequence("Ctrl+1"), self,
                  activated=lambda: self._navigate(0))
        QShortcut(QKeySequence("Ctrl+2"), self,
                  activated=lambda: self._navigate(1))

    # ---------------------------------------------------------- lifecycle
    def start(self):
        """Keep the startup API for compatibility; consent is already done."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _prepare_engine(self):
        if self._init_thread is not None and self._init_thread.isRunning():
            return
        if self._busy:
            QMessageBox.information(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("status.inferring"))
            return
        models_dir = Path(
            self.settings.data.get("models_dir", "") or BUNDLED_MODELS)
        self.settings.data["models_dir"] = ""
        self.settings.save()
        device = self.settings.data.get("device", "cpu")
        low_memory = bool(self.settings.data.get("low_memory", False))
        self._set_disabled_while_preparing()
        self.models_edit.setText(str(models_dir))
        self.load_progress.setRange(0, 10)
        self.load_progress.setValue(0)
        self._set_status(self.model_status_label, "status.preparing")
        self._set_status(self.status_label, "status.preparing")
        self._init_thread = EngineInitThread(
            models_dir, device, low_memory, self)
        self._init_thread.checkpoint_progress.connect(
            self._on_checkpoint_progress)
        self._init_thread.engine_ready.connect(self._on_engine_ready)
        self._init_thread.failed.connect(self._on_engine_failed)
        if self.engine is not None:
            previous = self.engine
            self.engine = None
            previous.cleanup()
        self._init_thread.start()

    def _set_disabled_while_preparing(self):
        self.single_run_btn.setEnabled(False)
        self.batch_run_btn.setEnabled(False)
        self.batch_export_btn.setEnabled(False)
        self.apply_settings_btn.setEnabled(False)

    @Slot(int, int)
    def _on_checkpoint_progress(self, done: int, total: int):
        if done < 0:
            self._set_status(self.model_status_label, "status.fallback")
            return
        if total:
            self.load_progress.setRange(0, total)
            self.load_progress.setValue(done)
            self._set_status(self.model_status_label, "status.loading",
                             done=done, total=total)

    @Slot(object)
    def _on_engine_ready(self, engine):
        if self._closing:
            if engine is not None:
                engine.cleanup()
            self._dispose_init_thread()
            return
        self.engine = engine
        status = engine.status()
        self.load_progress.setRange(0, status.checkpoint_count)
        self.load_progress.setValue(status.checkpoint_count)
        self.model_label.setText("{0} / {0}".format(status.checkpoint_count))
        self.backend_label.setText(status.active_device.upper())
        self._set_status(self.models_status, "settings.detected",
                         n=status.checkpoint_count)
        note_key = ""
        if status.active_device == "cpu" and \
                status.requested_device != "cpu":
            note_key = "status.fallback"
        elif status.requested_device != "cpu":
            note_key = "status.accelerator_warning"
        self._set_status(
            self.model_status_label, "status.prepared_detail",
            seconds=status.load_seconds, fingerprint=engine.fingerprint,
            note=self.i18n.tr(note_key) if note_key else "")
        self.fingerprint_label.setText(engine.fingerprint)
        self._set_status(self.status_label, "status.prepared")
        self.single_run_btn.setEnabled(True)
        self.apply_settings_btn.setEnabled(True)
        self._refresh_batch_actions()
        self._dispose_init_thread()

    @Slot(str)
    def _on_engine_failed(self, message: str):
        if self._closing:
            self._dispose_init_thread()
            return
        detail = localized_error(self.i18n, message)
        self._set_status(self.status_label, "status.error")
        if message == "error.no_checkpoints":
            self._set_status(self.model_status_label,
                              "error.no_checkpoints")
        else:
            self._set_status(self.model_status_label, "error.raw_detail",
                             detail=message)
        self.apply_settings_btn.setEnabled(True)
        self._dispose_init_thread()
        QMessageBox.critical(
            self, self.i18n.tr("common.error"),
            self.model_status_label.text())

    def _dispose_init_thread(self):
        thread = self._init_thread
        if thread is None:
            return
        thread.checkpoint_progress.disconnect()
        thread.engine_ready.disconnect()
        thread.failed.disconnect()
        if thread.isRunning():
            thread.wait()
        thread.deleteLater()
        self._init_thread = None

    def closeEvent(self, event):  # noqa: D102, N802
        self._closing = True
        for thread in (self._active_thread, self._init_thread):
            if thread is not None and thread.isRunning():
                if thread is self._init_thread:
                    thread.wait()
                else:
                    thread.wait(3000)
        if self.engine is not None:
            self.engine.cleanup()
        super().closeEvent(event)

    # ----------------------------------------------------------- helpers
    def _pick_nifti(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self, self.i18n.tr("single.images"), "",
            self.i18n.tr("common.filter.nifti"))
        if path:
            edit.setText(path)

    def _pick_data_dir(self):
        default = self.batch_dir_edit.text() or str(Path.home())
        path = QFileDialog.getExistingDirectory(
            self, self.i18n.tr("batch.select_dir"), default)
        if path:
            self.batch_dir_edit.setText(path)
            self.settings.data["last_data_dir"] = path
            self.settings.save()

    def _choose_models_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, self.i18n.tr("settings.models_dir"),
            self.models_edit.text() or str(BUNDLED_MODELS))
        if path:
            self.models_edit.setText(path)

    def _open_first_image(self):
        self._pick_nifti(self.file_edits["dce_n4"])

    def _quick_toggle_language(self):
        new_lang = "en-US" if self.i18n.lang == "zh-CN" else "zh-CN"
        self._apply_language(new_lang, reload_engine=False)

    def _apply_language(self, language: str, reload_engine: bool = False):
        """Translate every live widget immediately; never recreate the window."""
        if language not in ("en-US", "zh-CN"):
            return
        self.i18n.set_language(language)
        self.settings.data["language"] = language
        self.settings.save()
        self.setWindowTitle(self.i18n.tr("app.short"))
        for widget, key, method in self._translations:
            getattr(widget, method)(self.i18n.tr(key))
        for table in (self.fold_table, self.batch_table):
            keys = table.property("header_keys")
            if keys:
                table.setHorizontalHeaderLabels(
                    [self.i18n.tr(key) for key in keys])
        for index, button in enumerate(self.nav_group.buttons()):
            button.setText(self.i18n.tr((
                "nav.single", "nav.batch", "nav.settings", "nav.about"
            )[index]))
        self.language_toggle.setToolTip(
            self.i18n.tr("common.switch_language"))
        index = self.language_combo.findData(language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        self.language_combo.setItemText(
            self.language_combo.findData("zh-CN"),
            self.i18n.tr("common.language_zh"))
        self.language_combo.setItemText(
            self.language_combo.findData("en-US"),
            self.i18n.tr("common.language_en"))
        self.device_combo.setItemText(
            self.device_combo.findData("cpu"),
            "CPU · " + self.i18n.tr("common.reference"))
        for widget in self.form_edits.values():
            if isinstance(widget, QComboBox):
                current = widget.currentData()
                for index in range(widget.count()):
                    value = widget.itemData(index)
                    widget.setItemText(index, self._value_text(value))
                found = widget.findData(current)
                if found >= 0:
                    widget.setCurrentIndex(found)
            else:
                widget.setPlaceholderText("0")
        for edit in self.file_edits.values():
            edit.setPlaceholderText(self.i18n.tr("common.missing"))
        self.batch_dir_edit.setPlaceholderText(
            self.i18n.tr("batch.dir_hint"))
        if self.preview_image.pixmap() is None:
            self.preview_image.setText(self.i18n.tr("common.preview_empty"))
        for widget, (key, kwargs) in list(self._dynamic_text.items()):
            widget.setText(self.i18n.tr(key, **kwargs))
        if self.status_label not in self._dynamic_text:
            self._set_status(self.status_label, "status.ready")
        if self.batch_status not in self._dynamic_text:
            self._set_status(self.batch_status, "batch.empty")
        self._dynamic_text.pop(self.import_table_status, None)
        self._dynamic_text.pop(self.run_log, None)
        self.import_table_status.setText("")
        self.run_log.setText("")
        self._refresh_version_label()
        self._refresh_coverage()
        self._refresh_structure_label()
        self._refresh_batch_result_translations()
        self._refresh_batch_rows()
        self._retranslate_result()
        _ = reload_engine  # Kept for API symmetry; callers reload explicitly.

    def _refresh_version_label(self):
        if hasattr(self, "version_label"):
            self.version_label.setText("{}  {}".format(
                self.i18n.tr("about.version"),
                self.i18n.tr("app.version")))

    def _refresh_structure_label(self):
        if hasattr(self, "structure_label"):
            self.structure_label.setText("{}\n{}".format(
                self.i18n.tr("common.directory_structure"),
                experiment_tree_description()))

    def _retranslate_result(self):
        result = getattr(self, "_last_single_result", None)
        if result is not None:
            self._show_single_result(result)

    def _refresh_batch_result_translations(self):
        for values in self._batch_result_rows.values():
            values[6] = self.i18n.tr(
                "values." + values[9], fallback=values[9])

    def _refresh_coverage(self):
        if not hasattr(self, "coverage_bar"):
            return
        row = {}
        for column, widget in self.form_edits.items():
            row[column] = widget.currentData() \
                if isinstance(widget, QComboBox) else widget.text().strip()
        report = clinical_coverage(row)
        quality = ("common.quality_high" if report.percent >= 90 else
                   "common.quality_medium" if report.percent >= 70 else
                   "common.quality_low" if report.percent >= 40 else
                   "common.quality_insufficient")
        text = self.i18n.tr(
            "single.coverage", filled=report.filled, total=report.total,
            quality=self.i18n.tr(quality))
        if report.missing:
            text += "\n" + self.i18n.tr(
                "single.coverage_missing", fields=", ".join(
                    self.i18n.tr(self._field_labels.get(
                        column, "common.optional"))
                    for column in report.missing))
        self.coverage_label.setText(text)
        self.coverage_bar.setValue(report.percent)

    def apply_settings(self):
        language = self.language_combo.currentData()
        self.settings.data["models_dir"] = self.models_edit.text().strip()
        self.settings.data["device"] = self.device_combo.currentData()
        self.settings.data["low_memory"] = self.low_memory_check.isChecked()
        self._apply_language(language, reload_engine=False)
        self._prepare_engine()

    # ------------------------------------------------------- single flow
    def import_clinical_table(self):
        from core.clinical_table import (
            ClinicalTableError, match_clinical_row, widget_value,
            localized_error,
        )

        path, _ = QFileDialog.getOpenFileName(
            self, self.i18n.tr("single.import_table_title"), "",
            self.i18n.tr("common.filter.excel"))
        if not path:
            return
        case_id = self.case_id_edit.text().strip()
        if not case_id:
            for edit in self.file_edits.values():
                text = edit.text().strip()
                if text:
                    candidate = Path(text).name.split("_DCE_N4")[0]
                    if candidate and candidate != Path(text).name:
                        case_id = candidate
                        self.case_id_edit.setText(case_id)
                        break
        try:
            match = match_clinical_row(path, case_id)
        except (ClinicalTableError, OSError) as exc:
            detail = localized_error(self.i18n, str(exc))
            self._set_status(self.import_table_status,
                             "single.import_failed", error=detail)
            QMessageBox.warning(
                self, self.i18n.tr("common.notice"), detail)
            return
        columns = _clinical_columns()
        if ClinicalImportDialog(
                self.i18n, match.row, match.source, columns,
                self, match.coverage).exec() != QDialog.Accepted:
            self._set_status(self.import_table_status,
                             "single.import_cancelled")
            return
        case_id = str(match.row.get("ID") or case_id)
        self.case_id_edit.setText(case_id)
        for column in columns:
            widget = self.form_edits[column]
            value = widget_value(column, match.row.get(column))
            if isinstance(widget, QComboBox):
                index = widget.findData(value)
                if index < 0:
                    widget.insertItem(0, value, value)
                    index = 0
                widget.setCurrentIndex(index)
            else:
                widget.setText(value)
        self._set_status(self.import_table_status,
                         "single.import_done", source=match.source)
        self._refresh_coverage()

    def _single_case(self) -> PatientCase | None:
        from core.engine import PatientCase

        for key, edit in self.file_edits.items():
            if not edit.text() or not Path(edit.text()).is_file():
                QMessageBox.warning(
                    self, self.i18n.tr("common.notice"),
                    self.i18n.tr("single.missing_files"))
                self._focus_file(key)
                return None
        case_id = self.case_id_edit.text().strip() or "case"
        row = {"ID": case_id}
        missing = []
        for column, widget in self.form_edits.items():
            value = widget.currentData() if isinstance(widget, QComboBox) \
                else widget.text().strip()
            if value == "":
                missing.append(self.i18n.tr(self._field_spec(column)[0]))
            row[column] = value
        if missing:
            QMessageBox.warning(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("single.missing_fields",
                             fields=", ".join(missing)))
            return None
        staged_root = Path(self.engine._scratch) / "single" / case_id
        image_dir = staged_root / "Positive" / case_id
        (image_dir / "MG").mkdir(parents=True, exist_ok=True)
        paths = {
            "dce_n4": image_dir / "{}_DCE_N4.nii.gz".format(case_id),
            "dce_decay": image_dir / "{}_DCE_decay1.nii.gz".format(case_id),
            "mlo": image_dir / "MG" / "{}_MG_MLO.nii.gz".format(case_id),
            "mlo_decay": image_dir / "MG" / "{}_MLO_decay1.nii.gz".format(case_id),
        }
        import shutil
        for key, target in paths.items():
            source = Path(self.file_edits[key].text())
            try:
                target.hardlink_to(source)
            except OSError:
                shutil.copyfile(source, target)
        return PatientCase(case_id=case_id, label_dir="Positive",
                           case_root=image_dir, table_row=row)

    def _focus_file(self, key: str):
        self.file_edits[key].setFocus()
        self._navigate(0)

    def run_single(self):
        if self.engine is None or self._busy:
            return
        case = self._single_case()
        if case is None:
            return
        problems = validate_case(case)
        if problems:
            QMessageBox.warning(
                self, self.i18n.tr("common.notice"),
                "; ".join(localized_problem(self.i18n, problem)
                          for problem in problems))
            return
        self.batch_cases = []
        self._begin_inference([case], single=True)

    def _begin_inference(self, cases: list[PatientCase], single: bool):
        from core.engine import PatientCase  # noqa: F401 - annotation boundary
        self._busy = True
        self._fold_progress_count = 0
        self.single_run_btn.setEnabled(False)
        self.batch_run_btn.setEnabled(False)
        self.batch_export_btn.setEnabled(False)
        self.apply_settings_btn.setEnabled(False)
        self._set_status(self.status_label, "status.inferring")
        self.single_progress.setVisible(True)
        self.single_progress.setRange(0, self.engine.checkpoint_count)
        self.single_progress.setValue(0)
        self.batch_progress.setRange(0, len(cases))
        self.batch_progress.setValue(0)
        self._set_status(self.run_log, "single.stage_done")
        self._active_thread = InferThread(self.engine, cases, self)
        self._active_thread.progress_text.connect(self._on_infer_progress)
        self._active_thread.finished_ok.connect(
            lambda results: self._inference_done(results, single))
        self._active_thread.failed.connect(self._infer_failed)
        self._active_thread.start()

    @Slot(str)
    def _on_infer_progress(self, text: str):
        if self._closing:
            return
        if text == "stage":
            self._set_status(self.run_log, "single.stage_done")
        elif text.startswith("fold:"):
            self._fold_progress_count += 1
            done = min(self._fold_progress_count, self.single_progress.maximum())
            self.single_progress.setValue(done)
            self._set_status(
                self.run_log, "single.fold_done", done=done,
                total=self.single_progress.maximum())
        elif text.startswith("preprocess:") or text == "preprocess":
            self._fold_progress_count = 0
            self.single_progress.setValue(0)
            self._set_status(self.run_log, "single.preprocess_done")
        elif text.startswith("case:"):
            parts = text.split(":")
            if len(parts) == 4:
                self.batch_progress.setValue(int(parts[2]))
                self._set_status(
                    self.batch_status, "batch.progress", done=parts[2],
                    total=parts[3], case=parts[1])

    @Slot(list)
    def _inference_done(self, results, single: bool):
        if self._closing:
            return
        self._busy = False
        self.single_progress.setVisible(False)
        self.single_run_btn.setEnabled(True)
        self.apply_settings_btn.setEnabled(True)
        self._set_status(self.status_label, "status.complete")
        self.batch_progress.setValue(self.batch_progress.maximum())
        if single:
            self._show_single_result(results[0])
        else:
            self.batch_results = results
            labels = {c.case_id: c.label_dir for c in self.batch_cases}
            self._last_df = scan_results_to_dataframe(results, labels)
            self._populate_batch_results(results)
        self._refresh_batch_actions()
        self._dispose_active_thread()

    def _show_single_result(self, result):
        self._last_single_result = result
        self.result_empty.setVisible(False)
        self.result_body.setVisible(True)
        self.positive_prob.setText("{:.2f}%".format(result.prob_pos * 100))
        self.negative_prob.setText("{:.2f}%".format(result.prob_neg * 100))
        self.positive_bar.setValue(round(result.prob_pos * 1000))
        self.negative_bar.setValue(round(result.prob_neg * 1000))
        prediction_key = "values.Positive" if result.prediction == "Positive" \
            else "values.Negative"
        self.prediction_label.setText(
            self.i18n.tr(prediction_key,
                         fallback=result.prediction))
        self.prediction_label.setStyleSheet(
            "font-weight: 600; font-size: 12pt; color: {};".format(
                COLORS["positive"] if result.prediction == "Positive"
                else COLORS["negative"]))
        self.single_export_btn.setEnabled(True)
        self.fold_table.setRowCount(len(result.fold_probs))
        for row, (name, probs) in enumerate(result.fold_probs.items()):
            self.fold_table.setItem(row, 0, QTableWidgetItem(name))
            self.fold_table.setItem(
                row, 1, QTableWidgetItem("{:.6f}".format(probs[0])))
            self.fold_table.setItem(
                row, 2, QTableWidgetItem("{:.6f}".format(probs[1])))

    def export_single(self):
        if self._last_single_result is None:
            return
        default_dir = self.settings.data.get("last_export_dir") or str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.tr("common.export_csv"),
            str(Path(default_dir) / "samt_single_result.csv"),
            self.i18n.tr("common.filter.csv"))
        if path:
            labels = {self._last_single_result.case_id: "Positive"}
            scan_results_to_dataframe(
                [self._last_single_result], labels).to_csv(
                    path, index=False, encoding="utf-8-sig")
            self.settings.data["last_export_dir"] = str(Path(path).parent)
            self.settings.save()

    # -------------------------------------------------------- batch flow
    def scan_batch(self):
        from core.engine import discover_cases, validate_case

        data_dir = Path(self.batch_dir_edit.text().strip())
        if not data_dir.is_dir():
            QMessageBox.information(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("batch.dir_hint"))
            return
        root, selected_case = resolve_experiment_root(data_dir)
        cases, problems = discover_cases(root, only_case=selected_case)
        self._case_rows, catalog_problems = catalog_cases(
            root, only_case=selected_case)
        if catalog_problems and not problems:
            problems = catalog_problems
        self.batch_cases = cases
        self.batch_results = []
        self._last_df = None
        self._batch_result_rows = {}
        self.batch_table.setRowCount(len(self._case_rows))
        self._refresh_batch_rows()
        if problems:
            self._set_status(
                self.batch_status, "batch.scan_problems",
                problems="; ".join(localized_problem(self.i18n, problem)
                                   for problem in problems))
        else:
            self._set_status(
                self.batch_status, "batch.found",
                n=len(self._case_rows))
        self._refresh_structure_label()
        self._refresh_batch_actions()

    def _refresh_batch_rows(self):
        if not hasattr(self, "batch_table"):
            return
        valid = {case.case_id: case for case in self.batch_cases}
        for index, item in enumerate(getattr(self, "_case_rows", [])):
            case = valid.get(item.case_id)
            inputs = 4 - len(item.missing)
            if case is not None and not item.missing:
                status = self.i18n.tr("batch.status_ok")
            else:
                fields = ", ".join(localized_problem(self.i18n, problem)
                                   for problem in item.missing)
                status = self.i18n.tr("batch.status_missing", fields=fields)
            values = [item.case_id,
                      self.i18n.tr("values." + item.label_dir,
                                   fallback=item.label_dir),
                      "{} / 4".format(inputs), status, "", "", "", ""]
            result_values = self._batch_result_rows.get(item.case_id)
            if result_values is not None:
                for column, value in result_values.items():
                    if column == 9:
                        continue
                    values[column] = value
            for column, value in enumerate(values):
                self.batch_table.setItem(
                    index, column, QTableWidgetItem(value))

    def _refresh_batch_actions(self):
        from core.engine import validate_case

        runnable = [c for c in self.batch_cases if not validate_case(c)]
        self.batch_run_btn.setEnabled(
            self.engine is not None and not self._busy and bool(runnable))
        self.batch_export_btn.setEnabled(
            self._last_df is not None and not self._busy)

    def run_batch(self):
        from core.engine import validate_case

        if self.engine is None or self._busy:
            return
        runnable = [c for c in self.batch_cases if not validate_case(c)]
        if not runnable:
            QMessageBox.information(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("batch.no_runnable"))
            return
        self._begin_inference(runnable, single=False)

    def _populate_batch_results(self, results):
        by_id = {r.case_id: r for r in results}
        self._batch_result_rows = {}
        for row in range(self.batch_table.rowCount()):
            item = self.batch_table.item(row, 0)
            if item is None:
                continue
            result = by_id.get(item.text())
            if result is None:
                continue
            values = {
                4: "{:.6f}".format(result.prob_neg),
                5: "{:.6f}".format(result.prob_pos),
                6: "",
                7: str(len(result.fold_probs)),
                9: result.prediction,
            }
            self._batch_result_rows[result.case_id] = values
            values[6] = self.i18n.tr("values." + result.prediction,
                                     fallback=result.prediction)
            for column, value in values.items():
                if column == 9:
                    continue
                self.batch_table.setItem(
                    row, column, QTableWidgetItem(value))

    def export_batch(self):
        if self._last_df is None:
            return
        default_dir = self.settings.data.get("last_export_dir") or str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self, self.i18n.tr("common.export_csv"),
            str(Path(default_dir) / "samt_results.csv"),
            self.i18n.tr("common.filter.csv"))
        if path:
            self._last_df.to_csv(path, index=False, encoding="utf-8-sig")
            self.settings.data["last_export_dir"] = str(Path(path).parent)
            self.settings.save()

    @Slot(str)
    def _infer_failed(self, message: str):
        if self._closing:
            return
        self._busy = False
        self.single_progress.setVisible(False)
        self.single_run_btn.setEnabled(True)
        self.apply_settings_btn.setEnabled(True)
        self._refresh_batch_actions()
        self._set_status(self.status_label, "status.error")
        if message == "error.no_checkpoints":
            self._set_status(self.run_log, "error.no_checkpoints")
        else:
            self._set_status(self.run_log, "error.raw_detail",
                             detail=message)
        self._dispose_active_thread()
        QMessageBox.critical(
            self, self.i18n.tr("common.error"), self.run_log.text())

    def _dispose_active_thread(self):
        thread = self._active_thread
        if thread is None:
            return
        try:
            thread.progress_text.disconnect()
            thread.finished_ok.disconnect()
            thread.failed.disconnect()
        except RuntimeError:
            pass
        if thread.isRunning():
            thread.wait()
        thread.deleteLater()
        self._active_thread = None
