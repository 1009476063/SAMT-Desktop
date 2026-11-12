"""Operator review of an imported SAMT CP.xlsx row before autofill."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)


class ClinicalImportDialog(QDialog):
    def __init__(self, i18n, row: dict, source: str, columns: list[str],
                 coverage=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("single.import_review_title"))
        self.setMinimumSize(620, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        filled = coverage.filled if coverage else sum(
            bool(row.get(column)) for column in columns)
        summary = QLabel(i18n.tr("single.import_review_summary",
                                 source=source, total=len(columns),
                                 filled=filled))
        summary.setWordWrap(True)
        layout.addWidget(summary)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(coverage.percent if coverage else
                     round(filled * 100 / max(1, len(columns))))
        bar.setFormat("%v%")
        layout.addWidget(bar)

        table = QTableWidget(len(columns), 2)
        table.setHorizontalHeaderLabels([
            i18n.tr("single.import_column"), i18n.tr("single.import_value")])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for index, column in enumerate(columns):
            value = row.get(column, "")
            table.setItem(index, 0, QTableWidgetItem(repr(column)))
            table.setItem(index, 1, QTableWidgetItem(str(value)))
        layout.addWidget(table, 1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(i18n.tr("common.cancel"))
        cancel.clicked.connect(self.reject)
        apply_btn = QPushButton(i18n.tr("single.import_apply"))
        apply_btn.setProperty("role", "primary")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(apply_btn)
        layout.addLayout(buttons)
