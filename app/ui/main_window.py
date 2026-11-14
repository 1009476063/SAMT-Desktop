"""SAMT Desktop main window: a focused, bilingual research workbench."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QSize, Qt, QThread, QThreadPool, QTimer, QUrl, Signal, Slot,
)
from PySide6.QtGui import (
    QColor, QDesktopServices, QIcon, QImage, QKeySequence, QPainter, QPixmap,
    QShortcut, QTextOption,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox,
    QDialog, QFileDialog, QFormLayout, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSlider, QStackedWidget,
    QStyle, QTableWidget, QTableWidgetItem, QTextBrowser, QToolButton,
    QVBoxLayout, QWidget,
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
from core.preprocessing import (  # noqa: E402
    PreprocessingError, find_mlo_image, find_source_inputs,
    prepare_case_inputs, prepare_clinical_table,
)
from ui.clinical_import_dialog import ClinicalImportDialog  # noqa: E402
from ui.image_preview import ImagePreviewError, preview_pixmap  # noqa: E402
from ui.image_viewer import ImageVolumeViewer, input_display_name  # noqa: E402
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
    from PySide6.QtGui import QPen

    pen = QPen(QColor("#c9e7e2"))
    pen.setWidthF(1.6)
    painter.setPen(pen)
    painter.drawEllipse(4, 4, 24, 24)
    painter.drawLine(4, 16, 28, 16)
    painter.drawLine(16, 4, 16, 28)
    painter.drawArc(9, 4, 14, 24, 65 * 16, 230 * 16)
    painter.end()
    return QIcon(pixmap)


def _copy_icon() -> QIcon:
    """Draw the two-sheet copy glyph used by the tree code block."""
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.white)
    painter.drawRoundedRect(4, 4, 12, 16, 2, 2)
    painter.drawRoundedRect(9, 8, 11, 12, 2, 2)
    painter.end()
    return QIcon(pixmap)


def _standard_icon(name: str) -> QIcon:
    """Use a native platform glyph for a familiar command."""
    application = QApplication.instance()
    if application is not None:
        return application.style().standardIcon(getattr(QStyle, name))
    return QIcon()


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
            "background: {}; color: white; border-radius: 8px; "
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
        self.cancel_btn.setIcon(_standard_icon("SP_DialogCancelButton"))
        self.cancel_btn.clicked.connect(self.reject)
        self.enter_btn = QPushButton(self.i18n.tr("disclaimer.enter"))
        self.enter_btn.setProperty("role", "primary")
        self.enter_btn.setIcon(_standard_icon("SP_DialogApplyButton"))
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

    def _study_root(self):
        for case in self.cases:
            root = Path(case.case_root)
            for parent in (root, *root.parents):
                if (parent / "CP.xlsx").is_file() and \
                        (parent / "MRMG").is_dir():
                    return parent
        return None

    def run(self):
        try:
            self.progress_text.emit("stage")
            self.progress_text.emit("preprocess")
            from core.preprocessing import (
                PreprocessingError, prepare_case_inputs,
                prepare_clinical_table, preparing_status,
            )

            prepared = []
            scratch = Path(getattr(self.engine, "_scratch", "") or
                           tempfile.gettempdir())
            root = self._study_root()
            if root is not None:
                table, derived = prepare_clinical_table(
                    root, scratch / "prepared" / "CP.xlsx")
                if derived:
                    self.progress_text.emit(
                        "prepare:preprocess.clinical.running:{}".format(
                            derived))
                    for case in self.cases:
                        case.clinical_table = table
            for case in self.cases:
                self.progress_text.emit(
                    "prepare:preprocess.prepare:{}".format(case.case_id))
                result = prepare_case_inputs(
                    case.case_root, case.case_id,
                    progress=self.progress_text.emit,
                    output_root=scratch / "prepared" / case.case_id)
                if not result.complete:
                    raise PreprocessingError(
                        "prepare.incomplete:{}:{}".format(
                            case.case_id, preparing_status(result)))
                case.dce_n4 = result.dce_n4
                case.dce_decay = result.dce_decay
                case.mlo = result.mlo
                case.mlo_decay = result.mlo_decay
                prepared.append(result)
            self.progress_text.emit("prepare:complete:{}".format(
                sum(len(item.generated) for item in prepared)))
            results = self.engine.infer_staged_batch(
                self.cases, progress=self.progress_text.emit)
            self.finished_ok.emit(results)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class PrepareThread(QThread):
    """Run N4 and contour preprocessing away from the UI thread."""

    progress_text = Signal(str)
    finished_ok = Signal(object)
    failed = Signal(str)

    def __init__(self, source: Path, case_id: str,
                 output_root: Path | None = None, parent=None,
                 work=None):
        super().__init__(parent)
        self.source = source
        self.case_id = case_id
        self.output_root = output_root
        self.work = work

    def run(self):
        from core.preprocessing import prepare_case_inputs

        try:
            if self.work is not None:
                self.work(self.progress_text.emit)
                self.finished_ok.emit(None)
                return
            prepared = prepare_case_inputs(
                self.source, self.case_id,
                progress=self.progress_text.emit,
                output_root=self.output_root)
            self.finished_ok.emit(prepared)
        except Exception as exc:  # pragma: no cover - surfaced by UI
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
        self._case_source_root = None
        self._single_prepared = None
        self._translations: list[tuple[QWidget, str, str]] = []
        self._dynamic_text: dict[QWidget, tuple[str, dict]] = {}
        self._field_labels: dict[str, str] = {}
        self._case_rows: list = []
        self._batch_result_rows: dict[str, dict[int, str]] = {}
        self._last_df = None
        self._last_single_result = None
        self._active_thread = None
        self._init_thread = None
        self._prepare_thread = None
        self._prepare_context = None
        self._closing = False
        self._busy = False
        self._build_ui()
        self._connect_shortcuts()
        self._prepare_engine()

    # ------------------------------------------------------------ UI setup
    def _build_ui(self):
        self.setWindowTitle(self.i18n.tr("app.short"))
        self.setMinimumSize(1180, 760)
        self.resize(1460, 900)
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

    def _probability_text(self, probability: float) -> str:
        """Keep six decimals in both locales; never hide a close margin."""
        return "{:.6f} · {:.4f}%".format(probability, probability * 100)

    @staticmethod
    def _vote_split(result) -> tuple[int, int]:
        votes = [probs for probs in result.fold_probs.values()
                 if probs is not None]
        positive = sum(1 for probs in votes if probs[1] > probs[0])
        return positive, len(votes) - positive

    def _criticality_text(self, result) -> str:
        positive, negative = self._vote_split(result)
        margin = abs(result.prob_pos - 0.5)
        text = self.i18n.tr(
            "result.criticality", positive=positive, negative=negative,
            margin="{:.6f}".format(margin))
        if positive == negative or margin < 0.01:
            text += "\n" + self.i18n.tr("result.margin_explanation")
        return text

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
        self.language_toggle.setFixedSize(38, 34)
        self.language_toggle.setProperty("role", "header_tool")
        self.language_toggle.setToolTip(
            self.i18n.tr("common.switch_language"))
        self.language_toggle.clicked.connect(self._quick_toggle_language)
        row.addWidget(self.language_toggle)
        return header

    def _build_rail(self) -> QFrame:
        rail = QFrame()
        rail.setProperty("role", "rail")
        rail.setFixedWidth(200)
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
        if index == 1:
            QTimer.singleShot(0, self._fit_batch_buttons)

    @staticmethod
    def _page_scroll(widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
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
        self.single_top = QGridLayout()
        self.single_top.setSpacing(12)
        self.single_input_panel = self._build_single_input_panel()
        self.single_workspace_panel = self._build_single_workspace_panel()
        self.single_top.addWidget(self.single_input_panel, 0, 0)
        self.single_top.addWidget(self.single_workspace_panel, 0, 1)
        self.single_top.setColumnStretch(0, 7)
        self.single_top.setColumnStretch(1, 5)
        self.single_top.setColumnMinimumWidth(0, 360)
        self.single_top.setColumnMinimumWidth(1, 300)
        root.addLayout(self.single_top, 3)
        root.addWidget(self._build_fold_panel(), 1)
        scroll = self._page_scroll(page)
        QTimer.singleShot(0, self._sync_single_layout)
        return scroll

    def resizeEvent(self, event):  # noqa: D102, N802
        super().resizeEvent(event)
        self._sync_single_layout()

    def showEvent(self, event):  # noqa: D102, N802
        super().showEvent(event)
        QTimer.singleShot(0, self._sync_single_layout)

    def _sync_single_layout(self):
        try:
            if not hasattr(self, "single_top"):
                return
            stacked = self.width() < 1280
            if getattr(self, "_single_stacked", None) == stacked:
                return
            self._single_stacked = stacked
            for widget in (self.single_input_panel,
                           self.single_workspace_panel):
                self.single_top.removeWidget(widget)
            if stacked:
                self.single_top.addWidget(self.single_input_panel, 0, 0)
                self.single_top.addWidget(self.single_workspace_panel, 1, 0)
                self.single_top.setColumnStretch(0, 1)
                self.single_top.setColumnStretch(1, 0)
                self.single_top.setColumnMinimumWidth(1, 0)
                self.single_input_panel.setSizePolicy(
                    QSizePolicy.Ignored, QSizePolicy.Preferred)
                self.single_workspace_panel.setSizePolicy(
                    QSizePolicy.Expanding, QSizePolicy.Preferred)
            else:
                self.single_top.addWidget(self.single_input_panel, 0, 0)
                self.single_top.addWidget(self.single_workspace_panel, 0, 1)
                self.single_top.setColumnStretch(0, 7)
                self.single_top.setColumnStretch(1, 5)
                self.single_top.setColumnMinimumWidth(1, 300)
                self.single_input_panel.setSizePolicy(
                    QSizePolicy.Preferred, QSizePolicy.Preferred)
                self.single_workspace_panel.setSizePolicy(
                    QSizePolicy.Ignored, QSizePolicy.Preferred)
        except RuntimeError:
            return

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
        files_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for key, label_key in [
            ("dce_n4", "single.dce_n4"),
            ("dce_decay", "single.dce_decay"),
            ("mlo", "single.mlo"),
            ("mlo_decay", "single.mlo_decay"),
        ]:
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setReadOnly(True)
            edit.setMinimumWidth(0)
            edit.setPlaceholderText(self.i18n.tr("common.missing"))
            browse = self._tracked(QPushButton(), "common.browse")
            browse.setFixedWidth(92)
            browse.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            browse.setIcon(_standard_icon("SP_DirOpenIcon"))
            browse.clicked.connect(lambda _, e=edit: self._pick_nifti(e))
            edit.textChanged.connect(self._update_single_viewer)
            row.addWidget(edit, 1)
            row.addWidget(browse)
            label = self._tracked(QLabel(), label_key)
            label.setMinimumWidth(0)
            label.setMaximumWidth(156)
            files_form.addRow(label, row)
            self.file_edits[key] = edit
        layout.addLayout(files_form)
        layout.addWidget(_divider())
        case_row = QHBoxLayout()
        case_row.addWidget(self._tracked(QLabel(), "single.case_id"))
        self.case_id_edit = QLineEdit()
        self.case_id_edit.setMinimumWidth(0)
        self.case_id_edit.setPlaceholderText("")
        case_row.addWidget(self.case_id_edit, 1)
        layout.addLayout(case_row)
        self.single_source_btn = self._tracked(
            QPushButton(), "single.select_source")
        self.single_source_btn.setProperty("role", "subtle")
        self.single_source_btn.setIcon(_standard_icon("SP_DirOpenIcon"))
        self.single_source_btn.clicked.connect(self._select_source_folder)
        self.single_source_status = _caption("")
        source_row = QHBoxLayout()
        source_row.addWidget(self.single_source_btn)
        source_row.addWidget(self.single_source_status, 1)
        layout.addLayout(source_row)
        self.preprocess_note = self._tracked(
            _caption(""), "preprocess.note")
        layout.addWidget(self.preprocess_note)
        layout.addWidget(self._tracked(
            _caption(""), "single.case_id_hint"))
        table_row = QHBoxLayout()
        self.import_table_btn = self._tracked(
            QPushButton(), "single.import_table")
        self.import_table_btn.setIcon(_standard_icon("SP_DriveHDIcon"))
        self.import_table_btn.clicked.connect(self.import_clinical_table)
        self.import_table_status = _caption("")
        table_row.addWidget(self.import_table_btn)
        table_row.addWidget(self.import_table_status, 1)
        layout.addLayout(table_row)
        variables = QHBoxLayout()
        variables.setSpacing(16)
        clinical = self._build_form_group(
            "single.clinical", CLINICAL_COLUMNS)
        pathology = self._build_form_group(
            "single.pathology", PATHOLOGY_COLUMNS)
        clinical.setMinimumWidth(0)
        pathology.setMinimumWidth(0)
        clinical.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        pathology.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        variables.addWidget(clinical, 1)
        variables.addWidget(pathology, 1)
        layout.addLayout(variables)
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
        layout.addStretch(1)
        action = QHBoxLayout()
        action.addStretch(1)
        self.single_run_btn = self._tracked(QPushButton(), "single.run")
        self.single_run_btn.setProperty("role", "primary")
        self.single_run_btn.setIcon(_standard_icon("SP_MediaPlay"))
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
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)
        form.setLabelAlignment(Qt.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for column in columns:
            label_key, values = self._field_spec(column)
            if values:
                widget = QComboBox()
                widget.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToContents)
                widget.addItem(self.i18n.tr("common.select_placeholder"), "")
                for value in values:
                    widget.addItem(self._value_text(value), value)
            else:
                widget = QLineEdit()
                widget.setPlaceholderText("")
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            widget.setToolTip(column)
            widget.setAccessibleName(self.i18n.tr(label_key))
            label = self._tracked(QLabel(), label_key)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            label.setWordWrap(False)
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
        panel.setMinimumWidth(300)
        panel.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(self._tracked(
            _section_label(""), "preview.title"))
        self.preview_image = self._tracked(
            QLabel(), "common.preview_empty")
        self.preview_image.setAlignment(Qt.AlignCenter)
        self.preview_image.setMinimumHeight(220)
        self.preview_image.setMinimumWidth(0)
        self.preview_image.setSizePolicy(
            QSizePolicy.Ignored, QSizePolicy.Expanding)
        self.preview_image.setWordWrap(True)
        self.preview_image.setStyleSheet(
            "background: {}; border: 1px solid {}; border-radius: 5px;"
            .format(COLORS["surface_alt"], COLORS["border"]))
        layout.addWidget(self.preview_image, 1)
        preview_row = QHBoxLayout()
        self.preview_selector = self._tracked(
            QPushButton(), "common.preview")
        self.preview_selector.setIcon(
            _standard_icon("SP_FileDialogContentsView"))
        self.preview_selector.clicked.connect(self._show_image_preview)
        self.viewer_btn = self._tracked(
            QPushButton(), "viewer.open")
        self.viewer_btn.setIcon(_standard_icon("SP_ComputerIcon"))
        self.viewer_btn.setToolTip(self.i18n.tr("viewer.open_hint"))
        self.viewer_btn.clicked.connect(self._open_single_viewer)
        self.preview_shape = _caption("")
        preview_row.addWidget(self.preview_selector)
        preview_row.addWidget(self.viewer_btn)
        preview_row.addWidget(self.preview_shape, 1)
        layout.addLayout(preview_row)
        self.single_viewer_panel = QFrame()
        self.single_viewer_panel.setProperty("role", "subpanel")
        viewer_layout = QVBoxLayout(self.single_viewer_panel)
        viewer_layout.setContentsMargins(10, 8, 10, 8)
        viewer_layout.setSpacing(6)
        self.single_viewer_header = _caption("")
        viewer_layout.addWidget(self.single_viewer_header)
        self.single_plane_combo = QComboBox()
        for orientation in ("axial", "coronal", "sagittal"):
            self.single_plane_combo.addItem(
                self.i18n.tr("viewer.plane." + orientation), orientation)
        self.single_plane_combo.currentIndexChanged.connect(
            self._refresh_single_viewer)
        viewer_layout.addWidget(self.single_plane_combo)
        self.single_slice_slider = QSlider(Qt.Horizontal)
        self.single_slice_slider.valueChanged.connect(
            self._refresh_single_viewer)
        viewer_layout.addWidget(self.single_slice_slider)
        self.single_slice_label = _caption("")
        viewer_layout.addWidget(self.single_slice_label)
        self.single_viewer_panel.setVisible(False)
        layout.addWidget(self.single_viewer_panel)
        layout.addWidget(_divider())
        layout.addWidget(self._tracked(
            _section_label(""), "single.result"))
        self.result_empty = self._tracked(
            QLabel(), "single.empty_result")
        self.result_empty.setWordWrap(True)
        self.result_empty.setProperty("role", "caption")
        layout.addWidget(self.result_empty)
        self.result_empty.setStyleSheet(
            "background: {}; border: 1px dashed {}; border-radius: 6px; "
            "padding: 14px;".format(
                COLORS["accent_wash"], COLORS["border"]))
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
        self.single_criticality = _caption("")
        self.single_criticality.setWordWrap(True)
        self.single_criticality.setProperty("role", "result_note")
        result_layout.addWidget(self.single_criticality)
        self.result_body.setVisible(False)
        layout.addWidget(self.result_body)
        layout.addStretch(1)
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
        self.single_result_open_files_btn = self._tracked(
            QPushButton(), "viewer.open_files")
        self.single_result_open_files_btn.setIcon(
            _standard_icon("SP_DirOpenIcon"))
        self.single_result_open_files_btn.setEnabled(False)
        self.single_result_open_files_btn.clicked.connect(
            self._open_result_case_files)
        actions.addWidget(self.single_result_open_files_btn)
        self.single_export_btn = self._tracked(QPushButton(), "single.export")
        self.single_export_btn.setIcon(_standard_icon("SP_DialogSaveButton"))
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

    def _open_single_viewer(self):
        sources = {}
        hinted = False
        for key, edit in self.file_edits.items():
            path = edit.text().strip()
            if path and Path(path).is_file():
                sources[key] = path
                hinted = True
        if not hinted:
            self._pick_nifti(self.file_edits["dce_n4"])
            path = self.file_edits["dce_n4"].text().strip()
            if not path or not Path(path).is_file():
                return
            sources["dce_n4"] = path
        try:
            viewer = ImageVolumeViewer(
                self.i18n, sources, initial_key=next(iter(sources)),
                parent=self)
            viewer.exec()
        except (ImagePreviewError, OSError, ValueError) as exc:
            QMessageBox.warning(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("common.preview_failed", error=str(exc)))

    def _update_single_viewer(self):
        for key, edit in self.file_edits.items():
            path = edit.text().strip()
            if path and Path(path).is_file():
                self._single_viewer_key = key
                self._single_cached_path = path
                self._single_volume = None
                break
        else:
            self.single_viewer_panel.setVisible(False)
            return
        self.single_viewer_panel.setVisible(True)
        self._refresh_single_viewer()

    def _refresh_single_viewer(self, *_args):
        key = getattr(self, "_single_viewer_key", None)
        edit = self.file_edits.get(key)
        if edit is None or not edit.text() or not Path(edit.text()).is_file():
            self.single_viewer_panel.setVisible(False)
            return
        try:
            if getattr(self, "_single_cached_path", "") != edit.text():
                self._single_cached_path = edit.text()
                self._single_volume = None
            if getattr(self, "_single_volume", None) is None:
                from ui.image_preview import read_volume

                self._single_volume = read_volume(edit.text())
                self.single_slice_slider.blockSignals(True)
                self.single_slice_slider.setRange(
                    0, self._single_volume.shape[0] - 1
                    if len(self._single_volume.shape) == 3 else 0)
                self.single_slice_slider.setValue(
                    self.single_slice_slider.maximum() // 2)
                self.single_slice_slider.blockSignals(False)
            orientation = self.single_plane_combo.currentData()
            extent = self._single_volume.shape
            if len(extent) == 3:
                max_index = {
                    "axial": extent[0],
                    "coronal": extent[1],
                    "sagittal": extent[2],
                }[orientation] - 1
            else:
                max_index = 0
            if self.single_slice_slider.maximum() != max_index:
                self.single_slice_slider.blockSignals(True)
                self.single_slice_slider.setRange(0, max_index)
                self.single_slice_slider.setValue(max_index // 2)
                self.single_slice_slider.blockSignals(False)
            updated = self._single_volume.plane(
                orientation, self.single_slice_slider.value())
        except (ImagePreviewError, OSError, ValueError, ImportError) as exc:
            self.single_viewer_header.setText(self.i18n.tr(
                "common.preview_failed", error=str(exc)))
            return
        self.single_viewer_panel.setVisible(True)
        self.single_viewer_header.setText(self.i18n.tr(
            "viewer.source", name=input_display_name(self.i18n, key)))
        image = QImage(
            updated.gray.tobytes(), updated.gray.shape[1],
            updated.gray.shape[0], updated.gray.shape[1],
            QImage.Format_Grayscale8).copy()
        self.preview_image.setPixmap(QPixmap.fromImage(image).scaled(
            max(320, self.preview_image.width() - 20),
            max(220, self.preview_image.height() - 20),
            Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.single_slice_label.setText(self.i18n.tr(
            "viewer.slice", current=updated.index + 1,
            total=updated.max_index + 1,
            shape=" × ".join(str(value) for value in updated.shape),
            plane=self.i18n.tr(
                "viewer.plane." + self.single_plane_combo.currentData())))

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
        outer = QVBoxLayout(controls)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.settings.data.pop("last_data_dir", None)
        self.batch_dir_edit = QLineEdit()
        self.batch_dir_edit.setPlaceholderText(self.i18n.tr("batch.dir_hint"))
        browse = self._tracked(QPushButton(), "common.browse")
        browse.setIcon(_standard_icon("SP_DirOpenIcon"))
        browse.clicked.connect(self._pick_data_dir)
        self.batch_scan_btn = self._tracked(QPushButton(), "batch.scan")
        self.batch_scan_btn.setIcon(_standard_icon("SP_BrowserReload"))
        self.batch_scan_btn.clicked.connect(self.scan_batch)
        row.addWidget(self.batch_dir_edit, 1)
        row.addWidget(browse)
        row.addWidget(self.batch_scan_btn)
        outer.addLayout(row)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch(1)
        self.batch_prepare_btn = self._tracked(
            QPushButton(), "preprocess.prepare")
        self.batch_prepare_btn.setProperty("role", "subtle")
        self.batch_prepare_btn.setIcon(_standard_icon("SP_DialogApplyButton"))
        self.batch_run_btn = self._tracked(QPushButton(), "batch.run")
        self.batch_run_btn.setProperty("role", "primary")
        self.batch_run_btn.setIcon(_standard_icon("SP_MediaPlay"))
        self.batch_run_btn.clicked.connect(self.run_batch)
        self.batch_export_btn = self._tracked(QPushButton(), "batch.export")
        self.batch_export_btn.setIcon(_standard_icon("SP_DialogSaveButton"))
        self.batch_export_btn.clicked.connect(self.export_batch)
        self.batch_prepare_btn.clicked.connect(self.prepare_batch)
        actions.addWidget(self.batch_prepare_btn)
        actions.addWidget(self.batch_run_btn)
        actions.addWidget(self.batch_export_btn)
        outer.addLayout(actions)
        root.addWidget(controls)
        self.structure_title = self._tracked(
            _section_label(""), "common.directory_structure")
        root.addWidget(self.structure_title)
        self.structure_hint = self._tracked(
            _caption(""), "preprocess.tree_hint")
        root.addWidget(self.structure_hint)
        self.structure_copy = QToolButton()
        self.structure_copy.setIcon(_copy_icon())
        self.structure_copy.setIconSize(QSize(18, 18))
        self.structure_copy.setToolTip(
            self.i18n.tr("directory.copy_tree"))
        self.structure_copy.clicked.connect(self._copy_experiment_tree)
        self.structure_browser = QTextBrowser()
        self.structure_browser.setProperty("role", "tree")
        self.structure_browser.setReadOnly(True)
        self.structure_browser.setOpenExternalLinks(False)
        self.structure_browser.setWordWrapMode(QTextOption.NoWrap)
        self.structure_browser.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAsNeeded)
        self.structure_browser.setVerticalScrollBarPolicy(
            Qt.ScrollBarAsNeeded)
        self.structure_browser.setFixedHeight(142)
        tree_panel = QFrame()
        tree_panel.setProperty("role", "tree_panel")
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(0)
        copy_row = QHBoxLayout()
        copy_row.addStretch(1)
        copy_row.addWidget(self.structure_copy)
        tree_layout.addLayout(copy_row)
        tree_layout.addWidget(self.structure_browser)
        root.addWidget(tree_panel)
        self._refresh_structure_label()
        self.batch_table = QTableWidget(0, 8)
        self._set_table_headers(self.batch_table, (
            "batch.column_case", "batch.column_label",
            "batch.column_coverage", "batch.column_status",
            "batch.column_neg", "batch.column_pos",
            "batch.column_pred", "common.files"))
        self.batch_table.verticalHeader().setVisible(False)
        self.batch_table.verticalHeader().setDefaultSectionSize(46)
        self.batch_table.verticalHeader().setMinimumSectionSize(46)
        self.batch_table.verticalHeader().setSectionResizeMode(
            QHeaderView.Fixed)
        self.batch_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        batch_header = self.batch_table.horizontalHeader()
        batch_header.setSectionResizeMode(QHeaderView.Interactive)
        for column, width in enumerate((130, 110, 105, 220, 150, 150, 110,
                                        136)):
            self.batch_table.setColumnWidth(column, width)
        batch_header.setSectionResizeMode(3, QHeaderView.Stretch)
        batch_header.setSectionResizeMode(7, QHeaderView.Fixed)
        self.batch_table.setColumnWidth(7, 136)
        self.batch_table.setAlternatingRowColors(True)
        self.batch_table.setMinimumHeight(180)
        self.batch_table.setShowGrid(True)
        self.batch_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.batch_table.itemSelectionChanged.connect(
            self._refresh_batch_summary)
        root.addWidget(self.batch_table, 1)
        self.batch_result_panel = _panel()
        result_layout = QGridLayout(self.batch_result_panel)
        result_layout.setContentsMargins(18, 14, 18, 14)
        result_layout.setHorizontalSpacing(18)
        result_layout.setVerticalSpacing(6)
        self.batch_result_title = self._tracked(
            _section_label(""), "batch.result_title")
        result_layout.addWidget(self.batch_result_title, 0, 0, 1, 3)
        result_layout.addWidget(
            self._tracked(_caption(""), "single.prob_neg"), 1, 0)
        result_layout.addWidget(
            self._tracked(_caption(""), "single.prob_pos"), 1, 1)
        result_layout.addWidget(
            self._tracked(_caption(""), "single.prediction"), 1, 2)
        result_layout.addWidget(
            self._tracked(_caption(""), "batch.result_checkpoints"), 1, 3)
        self.batch_criticality = _caption("")
        self.batch_criticality.setWordWrap(True)
        self.batch_criticality.setProperty("role", "result_note")
        result_layout.addWidget(self.batch_criticality, 3, 0, 1, 5)
        self.batch_summary_negative = QLabel("--")
        self.batch_summary_positive = QLabel("--")
        self.batch_summary_prediction = QLabel("--")
        self.batch_summary_folds = QLabel("--")
        for label in (self.batch_summary_negative,
                      self.batch_summary_positive):
            label.setStyleSheet(
                "font-size: 15pt; font-weight: 600; color: {};".format(
                    COLORS["accent"]))
        self.batch_summary_prediction.setStyleSheet(
            "font-size: 12pt; font-weight: 600;")
        result_layout.addWidget(self.batch_summary_negative, 2, 0)
        result_layout.addWidget(self.batch_summary_positive, 2, 1)
        result_layout.addWidget(self.batch_summary_prediction, 2, 2)
        result_layout.addWidget(self.batch_summary_folds, 2, 3)
        self.batch_result_panel.setVisible(False)
        root.addWidget(self.batch_result_panel)
        viewer_actions = QHBoxLayout()
        self.batch_open_files_btn = self._tracked(
            QPushButton(), "viewer.open_files")
        self.batch_open_files_btn.setIcon(_standard_icon("SP_DirOpenIcon"))
        self.batch_open_files_btn.setToolTip(
            self.i18n.tr("viewer.open_files_hint"))
        self.batch_open_files_btn.clicked.connect(
            self._open_selected_case_files)
        self.batch_summary_note = _caption("")
        viewer_actions.addWidget(self.batch_open_files_btn)
        viewer_actions.addWidget(self.batch_summary_note, 1)
        self.batch_open_files_btn.setVisible(False)
        self.batch_summary_note.setVisible(False)
        root.addLayout(viewer_actions)
        self.batch_files_row = viewer_actions
        progress_row = QHBoxLayout()
        self.batch_progress = QProgressBar()
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_progress.setFormat("%p%")
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
        detect_btn.setIcon(_standard_icon("SP_BrowserReload"))
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
        self.apply_settings_btn.setIcon(_standard_icon("SP_DialogApplyButton"))
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
        for thread in (self._active_thread, self._init_thread,
                       self._prepare_thread):
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

    def _select_source_folder(self):
        """Populate all four single-case inputs from one raw study folder."""
        if self._prepare_thread is not None or self._busy:
            return
        path = QFileDialog.getExistingDirectory(
            self, self.i18n.tr("single.select_source_title"),
            str(Path.home()))
        if not path:
            return
        source = Path(path)
        case_id = self.case_id_edit.text().strip() or source.name
        output_root = Path(self.engine._scratch) / "single_prepared" / \
            case_id if self.engine is not None else None
        self._prepare_context = ("single", source, case_id)
        self.single_source_btn.setEnabled(False)
        self._set_status(
            self.single_source_status, "batch.preparing",
            case=case_id, product=self.i18n.tr("prepare.product.prepare"))
        self._prepare_thread = PrepareThread(
            source, case_id, output_root=output_root, parent=self)
        self._prepare_thread.progress_text.connect(
            self._on_prepare_progress)
        self._prepare_thread.finished_ok.connect(
            self._single_preparation_done)
        self._prepare_thread.failed.connect(self._preparation_failed)
        self._prepare_thread.start()

    def _single_preparation_done(self, prepared):
        source, case_id = self._prepare_context[1:]
        self._apply_single_prepared(prepared, source, case_id)
        self._dispose_prepare_thread()
        self.single_source_btn.setEnabled(True)

    def _apply_single_prepared(self, prepared, source: Path, case_id: str):
        if not prepared.complete:
            from core.preprocessing import preparing_status

            self._set_status(
                self.single_source_status,
                "single.source_incomplete",
                missing=localized_problem(
                    self.i18n, preparing_status(prepared)))
        else:
            generated = ", ".join(
                self.i18n.tr("inputs." + name, fallback=name)
                for name in prepared.generated)
            self._set_status(
                self.single_source_status, "single.source_ready",
                generated=generated or self.i18n.tr("common.none"))
        inputs = prepared.model_inputs
        mapping = {
            "dce_n4": inputs.get("DCE_N4"),
            "dce_decay": inputs.get("DCE_decay1"),
            "mlo": inputs.get("MLO"),
            "mlo_decay": inputs.get("MLO_decay1"),
        }
        for key, value in mapping.items():
            self.file_edits[key].setText(str(value) if value else "")
        self.case_id_edit.setText(case_id)
        self._case_source_root = source
        self._single_prepared = prepared
        self._fill_single_aln_diameter(source, case_id)
        self._refresh_coverage()

    def _fill_single_aln_diameter(self, source: Path, case_id: str):
        """Fill only the derived ALN diameter; leave every other field empty."""
        contour = find_source_inputs(source, case_id).dce_gtvnd1
        if contour is None:
            return
        from core.preprocessing import lowest_layer_aln_diameter

        try:
            diameter = lowest_layer_aln_diameter(contour)
        except (OSError, ValueError, PreprocessingError):
            return
        if diameter is None:
            return
        edit = self.form_edits.get(
            "max diameter with lowest layer of ALN")
        if edit is not None and not edit.text().strip():
            edit.setText(str(diameter))

    @Slot(str)
    def _on_prepare_progress(self, text: str):
        if self._closing or self._prepare_context is None:
            return
        mode = self._prepare_context[0]
        if not text.startswith("prepare:"):
            return
        _, code, detail = text.split(":", 2)
        action = code.rsplit(".", 2)[-2] if code.endswith(".running") \
            else "prepare"
        target = self.batch_status if mode == "batch" else \
            self.single_source_status
        self._set_status(
            target, "batch.preparing", case=detail,
            product=self.i18n.tr("prepare.product." + action,
                                 fallback=action))
        if mode == "single":
            self._set_status(self.run_log,
                             "preprocess.progress." + action)

    @Slot(str)
    def _preparation_failed(self, message: str):
        mode = self._prepare_context[0] if self._prepare_context else ""
        self._dispose_prepare_thread()
        if self._closing:
            return
        self.single_source_btn.setEnabled(True)
        self.batch_prepare_btn.setEnabled(True)
        self._refresh_batch_actions()
        detail = localized_problem(self.i18n, message)
        if mode == "single":
            self._set_status(self.single_source_status,
                             "single.source_error", error=detail)
        self._set_status(self.run_log, "error.raw_detail", detail=detail)
        self._set_status(self.batch_status, "error.raw_detail", detail=detail)
        QMessageBox.critical(self, self.i18n.tr("common.error"), detail)

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

    def _retranslate_viewers(self):
        orientation = self.single_plane_combo.currentData()
        self.single_plane_combo.blockSignals(True)
        self.single_plane_combo.clear()
        for name in ("axial", "coronal", "sagittal"):
            self.single_plane_combo.addItem(
                self.i18n.tr("viewer.plane." + name), name)
        index = self.single_plane_combo.findData(orientation)
        self.single_plane_combo.setCurrentIndex(max(0, index))
        self.single_plane_combo.blockSignals(False)
        self.viewer_btn.setToolTip(self.i18n.tr("viewer.open_hint"))
        self.batch_open_files_btn.setToolTip(
            self.i18n.tr("viewer.open_files_hint"))
        for row in range(self.batch_table.rowCount()):
            holder = self.batch_table.cellWidget(row, 7)
            button = holder.findChild(QPushButton) if holder else None
            if isinstance(button, QPushButton):
                button.setText(self.i18n.tr("viewer.open"))
                button.setToolTip(self.i18n.tr("viewer.open_hint"))
        self._refresh_batch_actions()

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
        for widget in self.form_edits.values():
            if isinstance(widget, QComboBox) and widget.count():
                widget.setItemText(
                    0, self.i18n.tr("common.select_placeholder"))
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
                    widget.setItemText(
                        index, self._value_text(value) if value else "")
                found = widget.findData(current)
                if found >= 0:
                    widget.setCurrentIndex(found)
            else:
                widget.setPlaceholderText("")
        for edit in self.file_edits.values():
            edit.setPlaceholderText(self.i18n.tr("common.missing"))
        self.batch_dir_edit.setPlaceholderText(
            self.i18n.tr("batch.dir_hint"))
        self.structure_copy.setToolTip(
            self.i18n.tr("directory.copy_tree"))
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
        self._retranslate_viewers()
        self._refresh_batch_result_translations()
        self._refresh_batch_rows()
        self._retranslate_result()
        self._refresh_batch_summary()
        _ = reload_engine  # Kept for API symmetry; callers reload explicitly.

    def _refresh_version_label(self):
        if hasattr(self, "version_label"):
            self.version_label.setText("{}  {}".format(
                self.i18n.tr("about.version"),
                self.i18n.tr("app.version")))

    def _refresh_structure_label(self):
        if hasattr(self, "structure_browser"):
            self.structure_browser.setPlainText(
                self.i18n.tr("directory.tree",
                             fallback=experiment_tree_description()))

    def _copy_experiment_tree(self):
        QApplication.clipboard().setText(
            self.structure_browser.toPlainText())

    def _retranslate_result(self):
        result = getattr(self, "_last_single_result", None)
        if result is not None:
            self._show_single_result(result)

    def _refresh_batch_result_translations(self):
        result_by_id = {result.case_id: result
                        for result in self.batch_results}
        for case_id, values in self._batch_result_rows.items():
            result = result_by_id.get(case_id)
            if result is not None:
                values[6] = self.i18n.tr(
                    "values." + result.prediction,
                    fallback=result.prediction)

    def _selected_batch_result(self):
        row = self.batch_table.currentRow()
        if row < 0:
            row = 0
        item = self.batch_table.item(row, 0)
        if item is None:
            return None
        case_id = item.text()
        return next((result for result in self.batch_results
                     if result.case_id == case_id), None)

    def _refresh_batch_summary(self):
        result = self._selected_batch_result()
        root = self._selected_case_root()
        self.batch_open_files_btn.setVisible(root is not None)
        self.batch_summary_note.setVisible(root is not None)
        self.batch_open_files_btn.setEnabled(root is not None)
        self.batch_summary_note.setText(self.i18n.tr(
            "batch.files_available",
            name=root.name if root is not None else ""))
        if result is None:
            self.batch_result_panel.setVisible(False)
            return
        self.batch_result_panel.setVisible(True)
        self.batch_summary_negative.setText(
            self._probability_text(result.prob_neg))
        self.batch_summary_positive.setText(
            self._probability_text(result.prob_pos))
        self.batch_criticality.setText(self._criticality_text(result))
        disk_case = next((case for case in self._case_rows
                          if case.case_id == result.case_id), None)
        if disk_case is not None and \
                result.prediction != disk_case.label_dir:
            self.batch_criticality.setText(
                self.batch_criticality.text() + " · " +
                self.i18n.tr("batch.label_mismatch"))
        self.batch_summary_prediction.setText(self.i18n.tr(
            "values." + result.prediction, fallback=result.prediction))
        self.batch_summary_folds.setText(
            "{} / 10".format(sum(
                value is not None for value in result.fold_probs.values())))

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
                           case_root=image_dir, table_row=row,
                           dce_n4=paths["dce_n4"],
                           dce_decay=paths["dce_decay"],
                           mlo=paths["mlo"],
                           mlo_decay=paths["mlo_decay"])

    def _focus_file(self, key: str):
        self.file_edits[key].setFocus()
        self._navigate(0)

    def run_single(self):
        from core.engine import validate_case

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
        self._inference_cases = list(cases)
        self._inference_single = single
        self._completed_case_count = 0
        self.single_run_btn.setEnabled(False)
        self.batch_run_btn.setEnabled(False)
        self.batch_export_btn.setEnabled(False)
        self.apply_settings_btn.setEnabled(False)
        self._set_status(self.status_label, "status.inferring")
        self.single_progress.setVisible(True)
        self.single_progress.setRange(0, self.engine.checkpoint_count)
        self.single_progress.setValue(0)
        self.batch_progress.setRange(0, 100)
        self.batch_progress.setValue(0)
        self.batch_result_panel.setVisible(False)
        self._set_status(
            self.batch_status, "batch.started", total=len(cases),
            case=cases[0].case_id if cases else "")
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
        elif text.startswith("prepare:"):
            _, code, detail = text.split(":", 2)
            if code.endswith(".running"):
                action = code.rsplit(".", 2)[-2]
                self._set_status(
                    self.batch_status, "batch.preparing",
                    case=detail, product=self.i18n.tr(
                        "prepare.product." + action, fallback=action))
                self._set_status(
                    self.run_log, "preprocess.progress." + action)
            elif code == "complete":
                self._set_status(
                    self.run_log, "preprocess.generated", n=detail)
        elif text.startswith("fold:"):
            self._fold_progress_count += 1
            done = min(self._fold_progress_count, self.single_progress.maximum())
            self.single_progress.setValue(done)
            total_folds = max(
                len(getattr(self, "_inference_cases", ()))
                * self.single_progress.maximum(), 1)
            elapsed_folds = (
                self._completed_case_count * self.single_progress.maximum()
                + done)
            percent = min(100, round(elapsed_folds * 100 / total_folds))
            self.batch_progress.setValue(percent)
            case_id = ""
            if getattr(self, "_inference_cases", None):
                case_id = self._inference_cases[min(
                    self._completed_case_count,
                    len(self._inference_cases) - 1)].case_id
            self._set_status(
                self.batch_status, "batch.fold_progress",
                percent=percent, fold=done, folds=self.single_progress.maximum(),
                case=case_id)
            self._set_status(
                self.run_log, "single.fold_done", done=done,
                total=self.single_progress.maximum())
        elif text.startswith("preprocess:") or text == "preprocess":
            self._fold_progress_count = 0
            self.single_progress.setValue(0)
            case_id = text.partition(":")[2]
            self._set_status(
                self.batch_status, "batch.preprocessing", case=case_id)
            self._set_status(self.run_log, "single.preprocess_done")
        elif text.startswith("case:"):
            parts = text.split(":")
            if len(parts) == 4:
                self._completed_case_count = int(parts[2])
                percent = min(
                    100, round(self._completed_case_count * 100
                               / max(int(parts[3]), 1)))
                self.batch_progress.setValue(percent)
                self._set_status(
                    self.batch_status, "batch.case_complete", done=parts[2],
                    total=parts[3], case=parts[1], percent=percent)

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
            self._set_status(
                self.batch_status, "batch.single_complete",
                case=results[0].case_id if results else "")
        else:
            self.batch_results = results
            labels = {c.case_id: c.label_dir for c in self.batch_cases}
            from core.engine import scan_results_to_dataframe

            self._last_df = scan_results_to_dataframe(results, labels)
            self._populate_batch_results(results)
            self._refresh_batch_rows()
            self._set_status(
                self.batch_status, "batch.complete", n=len(results))
        self._refresh_batch_actions()
        self._dispose_active_thread()

    def _show_single_result(self, result):
        self._last_single_result = result
        self.result_empty.setVisible(False)
        self.result_body.setVisible(True)
        self.positive_prob.setText(self._probability_text(result.prob_pos))
        self.negative_prob.setText(self._probability_text(result.prob_neg))
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
        self.single_criticality.setText(self._criticality_text(result))
        self.single_export_btn.setEnabled(True)
        self.single_result_open_files_btn.setEnabled(True)
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
            from core.engine import scan_results_to_dataframe

            scan_results_to_dataframe(
                [self._last_single_result], labels).to_csv(
                    path, index=False, encoding="utf-8-sig")
            self.settings.data["last_export_dir"] = str(Path(path).parent)
            self.settings.save()

    def _open_result_case_files(self):
        result = getattr(self, "_last_single_result", None)
        if result is None:
            return
        roots = {}
        for key, edit in self.file_edits.items():
            path = edit.text().strip()
            if path and Path(path).is_file():
                roots[key] = path
        if not roots:
            return
        parent = Path(next(iter(roots.values()))).parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(parent)))

    # -------------------------------------------------------- batch flow
    def prepare_batch(self):
        """Derive all available N4/decay products before prediction starts."""
        from core.engine import discover_cases

        if self._prepare_thread is not None or self._busy:
            return
        directory = self.batch_dir_edit.text().strip()
        if not directory or not Path(directory).is_dir():
            QMessageBox.information(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("batch.dir_hint"))
            return
        root, selected_case = resolve_experiment_root(directory)
        cases, problems = discover_cases(root, only_case=selected_case)
        if problems:
            self._set_status(self.batch_status, "batch.scan_problems",
                             problems="; ".join(localized_problem(
                                 self.i18n, problem)
                                 for problem in problems))
            return
        self.batch_cases = cases
        self._prepare_context = ("batch", Path(directory))
        self.batch_prepare_btn.setEnabled(False)
        self.batch_run_btn.setEnabled(False)
        self._prepare_thread = PrepareThread(
            Path(directory), "", parent=self,
            work=lambda progress: self._prepare_batch_cases(cases, progress))
        self._prepare_thread.progress_text.connect(
            self._on_prepare_progress)
        self._prepare_thread.finished_ok.connect(
            self._batch_preparation_done)
        self._prepare_thread.failed.connect(self._preparation_failed)
        self._prepare_thread.start()

    def _prepare_batch_cases(self, cases, progress):
        from core.preprocessing import preparing_status

        generated = []
        for case in cases:
            progress("prepare:preprocess.prepare.running:{}".format(
                case.case_id))
            prepared = prepare_case_inputs(
                case.case_root, case.case_id,
                progress=progress)
            generated.extend(prepared.generated)
            case.dce_n4 = prepared.dce_n4
            case.dce_decay = prepared.dce_decay
            case.mlo = prepared.mlo
            case.mlo_decay = prepared.mlo_decay
            if not prepared.complete:
                raise PreprocessingError(
                    "prepare.incomplete:{}:{}".format(
                        case.case_id, preparing_status(prepared)))
        self._prepared_product_count = len(generated)

    def _batch_preparation_done(self, _placeholder=None):
        self._dispose_prepare_thread()
        cases = self.batch_cases
        from core.contract_catalog import catalog_cases

        root, selected_case = resolve_experiment_root(
            self._prepare_context[1])
        self._case_rows, _ = catalog_cases(root, only_case=selected_case)
        self.batch_results = []
        self._last_df = None
        self._batch_result_rows = {}
        self.batch_table.setRowCount(len(self._case_rows))
        self._refresh_batch_rows()
        self.batch_prepare_btn.setEnabled(True)
        self.batch_run_btn.setEnabled(True)
        self._refresh_batch_actions()
        if all(case.dce_n4 and case.dce_decay and case.mlo and
               case.mlo_decay for case in cases):
            self._set_status(self.batch_status, "preprocess.batch_ready",
                             n=getattr(self, "_prepared_product_count", 0))

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
        self.batch_result_panel.setVisible(False)
        self.batch_table.setRowCount(len(self._case_rows))
        self._refresh_batch_rows()
        if self._case_rows:
            self.batch_table.selectRow(0)
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
        row_count = len(getattr(self, "_case_rows", []))
        if self.batch_table.rowCount() != row_count:
            self.batch_table.setRowCount(row_count)
        for stale_row in range(row_count):
            stale = self.batch_table.cellWidget(stale_row, 7)
            if stale is not None:
                stale.hide()
        self.batch_table.verticalHeader().setDefaultSectionSize(46)
        valid = {case.case_id: case for case in self.batch_cases}
        for index, item in enumerate(getattr(self, "_case_rows", [])):
            case = valid.get(item.case_id)
            inputs = 4 - len(item.missing)
            derivable_count = len(getattr(item, "derivable", ()))
            if case is not None and not item.missing:
                status = self.i18n.tr("batch.status_ok")
            elif derivable_count:
                names = ", ".join(
                    localized_problem(self.i18n, name)
                    for name in getattr(item, "derivable", ()))
                status = self.i18n.tr(
                    "batch.status_derivable", products=names)
            elif not item.missing and case is None:
                status = self.i18n.tr("batch.status_unavailable")
            else:
                fields = ", ".join(localized_problem(self.i18n, problem)
                                   for problem in item.missing)
                status = self.i18n.tr(
                    "batch.status_missing", fields=fields) if fields else ""
            disk_label = self.i18n.tr("values." + item.label_dir,
                                      fallback=item.label_dir)
            values = [item.case_id, disk_label,
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
            self._attach_batch_viewer(index, item.case_root)

            result = next((r for r in self.batch_results
                           if r.case_id == item.case_id), None)
            if result is not None and \
                    result.prediction != item.label_dir:
                for column in (1, 6):
                    table_item = self.batch_table.item(index, column)
                    if table_item is not None:
                        from PySide6.QtGui import QColor

                        table_item.setBackground(
                            QColor(COLORS["warning_soft"]))
                        table_item.setToolTip(self.i18n.tr(
                            "batch.label_mismatch"))
        for stale_row in range(len(self._case_rows), self.batch_table.rowCount()):
            stale = self.batch_table.cellWidget(stale_row, 7)
            if stale is not None:
                stale.hide()

    def _attach_batch_viewer(self, row: int, case_root: Path):
        existing = self.batch_table.cellWidget(row, 7)
        if existing is not None:
            existing.deleteLater()
            self.batch_table.setCellWidget(row, 7, None)
        button = QPushButton(self.i18n.tr("viewer.open"))
        button.setProperty("role", "small")
        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button.setFixedWidth(max(72, self.batch_table.columnWidth(7) - 16))
        button.setToolTip(self.i18n.tr("viewer.open_hint"))
        button.setAccessibleName(self.i18n.tr("viewer.open"))
        button.clicked.connect(
            lambda _, root=Path(case_root): self._open_case_viewer(root))
        holder = QWidget()
        holder.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 9, 0, 9)
        holder_layout.setSpacing(0)
        holder_layout.addWidget(button, 1, Qt.AlignVCenter)
        holder.show()
        self.batch_table.setCellWidget(row, 7, holder)
        QTimer.singleShot(
            0, lambda h=holder, b=button: self._fit_viewer_cell(h, b))

    def _fit_batch_buttons(self):
        width = max(72, self.batch_table.columnWidth(7) - 16)
        for row in range(self.batch_table.rowCount()):
            holder = self.batch_table.cellWidget(row, 7)
            button = holder.findChild(QPushButton) if holder else None
            if isinstance(button, QPushButton):
                button.setFixedWidth(width)
                self._fit_viewer_cell(holder, button)

    @staticmethod
    def _fit_viewer_cell(holder: QWidget, button: QPushButton):
        """Keep a row action inside its cell after Qt applies cell geometry."""
        try:
            visible = holder.isVisible()
        except RuntimeError:
            return
        if not visible:
            return
        button.setFixedWidth(max(72, holder.width() - 10))
        available = max(24, holder.height() - 18)
        button.setFixedHeight(min(28, available))
        holder_layout = holder.layout()
        if holder_layout is not None:
            holder_layout.activate()

    def _open_case_viewer(self, case_root: Path):
        from core.experiment_contract import REQUIRED_INPUT_GLOBS
        import glob

        sources = {}
        case_id = Path(case_root).name
        for key, pattern in REQUIRED_INPUT_GLOBS:
            matches = sorted(glob.glob(str(Path(case_root) / pattern.format(
                id=case_id))))
            if matches:
                sources[key] = matches[0]
        from core.preprocessing import find_source_inputs

        raw = find_source_inputs(case_root, case_id)
        for key, value in (("dce_raw", raw.dce_raw),
                           ("dce_gtv", raw.dce_gtv),
                           ("dce_gtvnd1", raw.dce_gtvnd1),
                           ("mlo_gtv", raw.mlo_gtv),
                           ("mlo_gtvnd1", raw.mlo_gtvnd1)):
            if value is not None:
                sources[key] = value
        if not sources:
            QMessageBox.information(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("viewer.no_images"))
            return
        try:
            viewer = ImageVolumeViewer(
                self.i18n, sources, initial_key=next(iter(sources)), parent=self)
            viewer.exec()
        except (ImagePreviewError, OSError, ValueError) as exc:
            QMessageBox.warning(
                self, self.i18n.tr("common.notice"),
                self.i18n.tr("common.preview_failed", error=str(exc)))

    def _selected_case_root(self) -> Path | None:
        row = self.batch_table.currentRow()
        if row < 0:
            row = 0
        item = self.batch_table.item(row, 0)
        if item is None:
            return None
        case = next((case for case in self.batch_cases
                     if case.case_id == item.text()), None)
        return Path(case.case_root) if case is not None else None

    def _open_selected_case_files(self):
        root = self._selected_case_root()
        if root is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(root)))

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
                6: self.i18n.tr("values." + result.prediction,
                                fallback=result.prediction),
            }
            self._batch_result_rows[result.case_id] = values
            for column, value in values.items():
                self.batch_table.setItem(
                    row, column, QTableWidgetItem(value))
        self._refresh_batch_summary()

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
        self.batch_progress.setFormat("%p%")
        self._set_status(self.status_label, "status.error")
        display_message = localized_problem(self.i18n, message) \
            if message.startswith(("source.", "prepare.", "shape:")) \
            else message
        if message == "error.no_checkpoints":
            self._set_status(self.run_log, "error.no_checkpoints")
        else:
            self._set_status(self.run_log, "error.raw_detail",
                             detail=display_message)
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

    def _dispose_prepare_thread(self):
        thread = self._prepare_thread
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
        self._prepare_thread = None
