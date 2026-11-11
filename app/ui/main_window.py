"""SAMT Desktop main window (PySide6)."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QStackedWidget, QTableWidget, QTableWidgetItem, QTabWidget,
    QTextEdit, QVBoxLayout, QWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from i18n import I18n  # noqa: E402
from settings import Settings  # noqa: E402
from core.engine import (  # noqa: E402
    CLINICAL_COLUMNS, PATHOLOGY_COLUMNS, PatientCase, discover_cases,
    validate_case, InferenceEngine,
)


APP_DIR = Path(__file__).resolve().parent.parent


def _bundled_models_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and (Path(meipass) / "models").is_dir():
        return Path(meipass) / "models"
    return APP_DIR / "models"


BUNDLED_MODELS = _bundled_models_dir()


class DisclaimerDialog(QDialog):
    def __init__(self, i18n: I18n, settings: Settings, parent=None):
        super().__init__(parent)
        self.i18n = i18n
        self.settings = settings
        self.setWindowTitle(self.i18n.tr("disclaimer.title"))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        body = QLabel(self.i18n.tr("disclaimer.body"))
        body.setWordWrap(True)
        layout.addWidget(body)
        self.checkbox = QCheckBox(self.i18n.tr("disclaimer.accept"))
        layout.addWidget(self.checkbox)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.enter_btn = QPushButton(self.i18n.tr("disclaimer.enter"))
        self.enter_btn.setEnabled(False)
        self.enter_btn.clicked.connect(self.accept)
        buttons.addWidget(self.enter_btn)
        layout.addLayout(buttons)
        self.checkbox.toggled.connect(self.enter_btn.setEnabled)

    def accept(self):  # noqa: D102
        self.settings.data["disclaimer_accepted"] = True
        self.settings.save()
        super().accept()


class InferThread(QThread):
    progress_text = Signal(str)
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, engine, cases, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.cases = cases

    def run(self):
        try:
            results = []
            total = len(self.cases)
            for i, case in enumerate(self.cases, 1):
                self.progress_text.emit(f"preprocess:{case.case_id}")
                result = self.engine.infer_case(case)
                results.append(result)
                self.progress_text.emit(f"case:{case.case_id}:{i}:{total}")
            self.finished_ok.emit(results)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = Settings()
        self.i18n = I18n(self.settings.data.get("language", ""))
        self.engine: InferenceEngine | None = None
        self.batch_cases = []
        self.batch_results = []
        self._build_ui()
        self._maybe_show_disclaimer()

    # ------------------------------------------------------------ UI setup
    def _build_ui(self):
        self.setWindowTitle(self.i18n.tr("app.name"))
        self.resize(960, 640)
        tabs = QTabWidget()
        self.tabs = tabs
        tabs.addTab(self._build_single_tab(), self.i18n.tr("mode.single"))
        tabs.addTab(self._build_batch_tab(), self.i18n.tr("mode.batch"))
        tabs.addTab(self._build_settings_tab(), self.i18n.tr("mode.settings"))
        tabs.addTab(self._build_about_tab(), self.i18n.tr("mode.about"))
        self.setCentralWidget(tabs)

    def _build_single_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        step1 = QGroupBox(self.i18n.tr("single.step1"))
        form = QFormLayout(step1)
        self.file_edits = {}
        for key, label_key in [
            ("dce_n4", "single.dce_n4"),
            ("dce_decay", "single.dce_decay"),
            ("mlo", "single.mlo"),
            ("mlo_decay", "single.mlo_decay"),
        ]:
            row = QHBoxLayout()
            edit = QLineEdit()
            btn = QPushButton(self.i18n.tr("single.browse"))
            btn.clicked.connect(lambda _, e=edit: self._pick_nifti(e))
            row.addWidget(edit, 1)
            row.addWidget(btn)
            form.addRow(QLabel(self.i18n.tr(label_key)), row)
            self.file_edits[key] = edit
        layout.addWidget(step1)

        step2 = QGroupBox(self.i18n.tr("single.step2"))
        form2 = QFormLayout(step2)
        self.form_edits = {}
        simple_fields = [
            ("case_id", "single.case_id", "text"),
            ("Laterality ", "Laterality", "combo:Left,Right"),
            ("Multifocality（Tumor number）", "Multifocality", "combo:Unifocal,Multifocal,Multicentric"),
            ("Location(nine)", "Location(nine)", "combo:UQ,OQ,LQ,IQ,UOQ,LOQ,LIQ,UIQ,CenP"),
            ("cT", "cT", "combo:T0,T1,T2,T3,T4"),
            ("Calcification", "Calcification", "combo:Yes,No"),
            ("Breast density ", "Breast density", "combo:A,B,C,D"),
            ("Age", "Age", "text"),
            ("Tumor size MRI ", "Tumor size MRI", "text"),
            ("max diameter with lowest layer of ALN", "ALN max diameter", "text"),
            ("Histological type  (needle biopsy)", "Histological type", "combo:Invasive ductal carcinoma,Invasive lobular carcinoma,Invasive carcinoma,Invasive micropapillary carcinoma,Ductal carcinoma in situ,Other"),
            ("Histological grade ", "Histological grade", "combo:I,II,III"),
            ("ER", "ER", "combo:+,-"),
            ("PR", "PR", "combo:+,-"),
            ("HER2", "HER2", "combo:+,-"),
            ("LVI", "LVI", "combo:Absent,Present"),
            ("Ki67", "Ki67", "combo:-,<20%,+,>=20%"),
            ("SLN-positive", "SLN positive count", "text"),
            ("total SLN", "Total SLN count", "text"),
            ("Positive_Total_SLN_ratio", "SLN ratio", "text"),
        ]
        for col, label, kind in simple_fields:
            if kind.startswith("combo:"):
                widget = QComboBox()
                widget.addItems(kind.split(":", 1)[1].split(","))
            else:
                widget = QLineEdit()
            form2.addRow(QLabel(label), widget)
            self.form_edits[col] = widget
        layout.addWidget(step2)

        run_row = QHBoxLayout()
        self.single_run_btn = QPushButton(self.i18n.tr("single.run"))
        self.single_run_btn.clicked.connect(self.run_single)
        run_row.addWidget(self.single_run_btn)
        run_row.addStretch(1)
        layout.addLayout(run_row)

        self.single_progress = QProgressBar()
        self.single_progress.setVisible(False)
        layout.addWidget(self.single_progress)
        self.single_output = QTextEdit()
        self.single_output.setReadOnly(True)
        layout.addWidget(self.single_output, 1)
        return w

    def _build_batch_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        dir_row = QHBoxLayout()
        self.batch_dir_edit = QLineEdit()
        self.batch_dir_btn = QPushButton(self.i18n.tr("single.browse"))
        self.batch_dir_btn.clicked.connect(self._pick_data_dir)
        self.batch_scan_btn = QPushButton(self.i18n.tr("batch.scan"))
        self.batch_scan_btn.clicked.connect(self.scan_batch)
        dir_row.addWidget(self.batch_dir_edit, 1)
        dir_row.addWidget(self.batch_dir_btn)
        dir_row.addWidget(self.batch_scan_btn)
        layout.addLayout(dir_row)

        self.batch_table = QTableWidget(0, 3)
        self.batch_table.setHorizontalHeaderLabels(["ID", "Label", "Status"])
        layout.addWidget(self.batch_table, 1)

        run_row = QHBoxLayout()
        self.batch_run_btn = QPushButton(self.i18n.tr("batch.run"))
        self.batch_run_btn.clicked.connect(self.run_batch)
        self.batch_export_btn = QPushButton(self.i18n.tr("batch.export"))
        self.batch_export_btn.clicked.connect(self.export_batch)
        self.batch_progress = QProgressBar()
        run_row.addWidget(self.batch_progress, 1)
        run_row.addWidget(self.batch_run_btn)
        run_row.addWidget(self.batch_export_btn)
        layout.addLayout(run_row)
        return w

    def _build_settings_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        form = QFormLayout()
        lang = QComboBox()
        lang.addItem("中文", "zh-CN")
        lang.addItem("English", "en-US")
        current = self.i18n.lang
        lang.setCurrentIndex(0 if current == "zh-CN" else 1)
        lang.currentIndexChanged.connect(self._change_language)
        form.addRow(QLabel(self.i18n.tr("settings.language")), lang)
        layout.addLayout(form)
        models_row = QHBoxLayout()
        self.models_edit = QLineEdit(self.settings.data.get("models_dir", ""))
        models_row.addWidget(self.models_edit, 1)
        detect_btn = QPushButton(self.i18n.tr("settings.detect"))
        detect_btn.clicked.connect(self.detect_models)
        models_row.addWidget(detect_btn)
        layout.addLayout(models_row)
        self.models_status = QLabel()
        layout.addWidget(self.models_status)
        layout.addStretch(1)
        return w

    def _build_about_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        text = QLabel(
            f"<h3>{self.i18n.tr('app.name')}</h3>"
            f"<p>{self.i18n.tr('about.research_only')}</p>"
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch(1)
        return w

    # ---------------------------------------------------------- lifecycle
    def _maybe_show_disclaimer(self):
        if not self.settings.data.get("disclaimer_accepted"):
            dlg = DisclaimerDialog(self.i18n, self.settings, self)
            dlg.exec()

    def _change_language(self, index: int):
        combo = self.sender()
        lang = combo.itemData(index)
        self.settings.data["language"] = lang
        self.settings.save()
        QMessageBox.information(self, self.i18n.tr("app.short"),
                                "Restart the app to apply the language change." if lang == "en-US"
                                else "重启应用后生效。")

    def detect_models(self):
        models_dir = Path(self.models_edit.text().strip() or BUNDLED_MODELS)
        try:
            engine = InferenceEngine(models_dir)
            count = engine.checkpoint_count
            self.engine = engine
            self.models_status.setText(self.i18n.tr("settings.detected", n=count))
            self.settings.data["models_dir"] = str(models_dir)
            self.settings.save()
        except Exception as exc:
            QMessageBox.critical(self, self.i18n.tr("common.error"), str(exc))

    # ----------------------------------------------------------- helpers
    def _pick_nifti(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(self, "NIfTI", "", "NIfTI (*.nii *.nii.gz)")
        if path:
            edit.setText(path)

    def _pick_data_dir(self):
        d = QFileDialog.getExistingDirectory(self, self.i18n.tr("batch.select_dir"))
        if d:
            self.batch_dir_edit.setText(d)

    # ------------------------------------------------------- single flow
    def run_single(self):
        if self.engine is None:
            self.detect_models()
        if self.engine is None:
            return
        case_id = self.form_edits["case_id"].text().strip() or "wizard_case"
        row = {"ID": case_id}
        for col, widget in self.form_edits.items():
            if col == "case_id":
                continue
            if isinstance(widget, QComboBox):
                row[col] = widget.currentText()
            else:
                row[col] = widget.text()
        case = PatientCase(case_id=case_id, label_dir="Positive",
                           case_root=Path("."), table_row=row)
        problems = [p for p in validate_case(case) if p.startswith("column:")]
        missing = [p.split(":", 1)[1] for p in problems]
        if missing:
            QMessageBox.warning(self, self.i18n.tr("common.error"),
                                "Missing fields: " + ", ".join(missing))
            return
        # Stage images into scratch with the on-disk layout dataset.py needs.
        staged_root = Path(self.engine._scratch) / "wizard" / case_id
        img_dir = staged_root / "Positive" / case_id
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / "MG").mkdir(exist_ok=True)
        import shutil
        shutil.copy(self.file_edits["dce_n4"].text(), img_dir / f"{case_id}_DCE_N4.nii.gz")
        shutil.copy(self.file_edits["dce_decay"].text(), img_dir / f"{case_id}_DCE_decay1.nii.gz")
        shutil.copy(self.file_edits["mlo"].text(), img_dir / "MG" / f"{case_id}_MG_MLO.nii.gz")
        shutil.copy(self.file_edits["mlo_decay"].text(), img_dir / "MG" / f"{case_id}_MLO_decay1.nii.gz")
        case.case_root = img_dir
        self.single_progress.setVisible(True)
        self.single_progress.setRange(0, 0)
        self.single_run_btn.setEnabled(False)
        self._thread = InferThread(self.engine, [case], self)
        self._thread.progress_text.connect(lambda t: self.single_output.append(t))
        self._thread.finished_ok.connect(self._single_done)
        self._thread.failed.connect(self._infer_failed)
        self._thread.start()

    def _single_done(self, results):
        self.single_progress.setVisible(False)
        self.single_run_btn.setEnabled(True)
        r = results[0]
        self.single_output.append(
            f"P(neg)={r.prob_neg:.4f}  P(pos)={r.prob_pos:.4f}  ->  {r.prediction}")

    def _infer_failed(self, message):
        self.single_progress.setVisible(False)
        self.single_run_btn.setEnabled(True)
        self.batch_run_btn.setEnabled(True)
        QMessageBox.critical(self, self.i18n.tr("common.error"), message)

    # -------------------------------------------------------- batch flow
    def scan_batch(self):
        data_dir = Path(self.batch_dir_edit.text().strip())
        cases, problems = discover_cases(data_dir)
        self.batch_cases = cases
        self.batch_table.setRowCount(len(cases))
        for i, c in enumerate(cases):
            self.batch_table.setItem(i, 0, QTableWidgetItem(c.case_id))
            self.batch_table.setItem(i, 1, QTableWidgetItem(c.label_dir))
            status = "OK" if not validate_case(c) else ";".join(validate_case(c))
            self.batch_table.setItem(i, 2, QTableWidgetItem(status))
        if not cases:
            QMessageBox.information(self, self.i18n.tr("app.short"),
                                    self.i18n.tr("batch.no_cases"))

    def run_batch(self):
        if not self.batch_cases:
            return
        if self.engine is None:
            self.detect_models()
        if self.engine is None:
            return
        runnable = [c for c in self.batch_cases if not validate_case(c)]
        self.batch_run_btn.setEnabled(False)
        self.batch_progress.setRange(0, len(runnable))
        self._thread = InferThread(self.engine, runnable, self)
        self._thread.progress_text.connect(self._batch_progress)
        self._thread.finished_ok.connect(self._batch_done)
        self._thread.failed.connect(self._infer_failed)
        self._thread.start()

    def _batch_progress(self, text):
        if text.startswith("case:"):
            _, case_id, done, total = text.split(":")
            self.batch_progress.setValue(int(done))

    def _batch_done(self, results):
        self.batch_run_btn.setEnabled(True)
        self.batch_results = results
        labels = {c.case_id: c.label_dir for c in self.batch_cases}
        df = self.engine.results_to_dataframe(results, labels)
        self._last_df = df
        self.batch_progress.setValue(self.batch_progress.maximum())

    def export_batch(self):
        if not hasattr(self, "_last_df") or self._last_df is None:
            return
        default_dir = self.settings.data.get("last_export_dir") or str(Path.home())
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV", str(Path(default_dir) / "samt_results.csv"), "CSV (*.csv)")
        if path:
            self._last_df.to_csv(path, index=False, encoding="utf-8-sig")
            self.settings.data["last_export_dir"] = str(Path(path).parent)
            self.settings.save()
