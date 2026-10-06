"""Review a date or numeric voucher range before deleting eligible records."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.voucher_deletion import (
    VoucherDeletionPreview,
    VoucherDeletionRange,
    VoucherDeletionRow,
)
from silverestimate.services.voucher_deletion import VoucherDeletionController
from silverestimate.ui.themed_controls import ThemedComboBox, ThemedDateEdit


class _PreviewModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: tuple[VoucherDeletionRow, ...] = ()
        self.completed = False

    def replace(self, rows, *, completed=False):
        self.beginResetModel()
        self.rows = rows
        self.completed = completed
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):  # noqa: B008
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):  # noqa: B008
        return 0 if parent.isValid() else 3

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role not in (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.ToolTipRole,
        ):
            return None
        row = self.rows[index.row()]
        status = (
            f"Kept: {row.skip_reason}"
            if row.skip_reason
            else ("Deleted" if self.completed else "Will be deleted")
        )
        return (row.voucher_no, row.date, status)[index.column()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return ("Voucher", "Date", "Result")[section]
        return None


class VoucherRangeDeletionDialog(QDialog):
    def __init__(self, controller: VoucherDeletionController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._preview: VoucherDeletionPreview | None = None
        self.setWindowTitle("Delete Vouchers by Range")
        self.resize(820, 560)
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "Both endpoints are included. Dates use the saved estimate date. "
            "Vouchers with assigned, issued, or transferred silver bars will be kept."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.mode = ThemedComboBox()
        self.mode.addItems(["Date range", "Voucher number range"])
        layout.addWidget(self.mode)
        self.fields = QStackedWidget()
        self.fields.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        dates, numbers = QWidget(), QWidget()
        date_layout, number_layout = QFormLayout(dates), QFormLayout(numbers)
        self.date_from, self.date_to = (
            ThemedDateEdit(QDate.currentDate()),
            ThemedDateEdit(QDate.currentDate()),
        )
        for field in (self.date_from, self.date_to):
            field.setCalendarPopup(True)
            field.setDisplayFormat("dd/MM/yyyy")
            field.dateChanged.connect(self._invalidate)
        self.voucher_from, self.voucher_to = QLineEdit(), QLineEdit()
        for number_field in (self.voucher_from, self.voucher_to):
            number_field.setPlaceholderText("Voucher number")
            number_field.textChanged.connect(self._invalidate)
        date_layout.addRow("From", self.date_from)
        date_layout.addRow("To", self.date_to)
        number_layout.addRow("From", self.voucher_from)
        number_layout.addRow("To", self.voucher_to)
        self.fields.addWidget(dates)
        self.fields.addWidget(numbers)
        layout.addWidget(self.fields)
        self.mode.currentIndexChanged.connect(self.fields.setCurrentIndex)
        self.mode.currentIndexChanged.connect(self._invalidate)
        self._build_results(layout)

    def _build_results(self, layout: QVBoxLayout) -> None:
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self._load_preview)
        layout.addWidget(self.preview_button)
        self.summary = QLabel("Choose a range, then preview the matching vouchers.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableView()
        self.model = _PreviewModel(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 110)
        self.table.verticalHeader().setDefaultSectionSize(48)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        self.delete_button = buttons.addButton(
            "Delete Eligible Vouchers…", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.delete_button.setObjectName("SettingsDangerButton")
        self.delete_button.setEnabled(False)
        self.delete_button.setAutoDefault(False)
        self.delete_button.clicked.connect(self._delete)
        layout.addWidget(buttons)

    def _invalidate(self, *_args):
        self._preview = None
        self.delete_button.setEnabled(False)
        self.model.replace(())
        self.summary.setText("Range changed. Preview the matching vouchers again.")

    def _criteria(self) -> VoucherDeletionRange:
        if self.mode.currentIndex() == 0:
            return VoucherDeletionRange(
                "date",
                self.date_from.date().toString("yyyy-MM-dd"),
                self.date_to.date().toString("yyyy-MM-dd"),
            )
        return VoucherDeletionRange(
            "voucher", self.voucher_from.text().strip(), self.voucher_to.text().strip()
        )

    def _load_preview(self):
        self._invalidate()
        try:
            preview = self.controller.preview(self._criteria(), self)
        except Exception as exc:
            QMessageBox.warning(self, "Preview Unavailable", str(exc))
            return
        self._preview = preview
        self.model.replace(preview.rows)
        self.summary.setText(
            f"Matched: {len(preview.rows)} • Eligible: {len(preview.eligible)} • Protected: {len(preview.skipped)}"
        )
        self.delete_button.setEnabled(bool(preview.eligible))

    def _confirm(self, preview: VoucherDeletionPreview) -> bool:
        bars = sum(row.bar_count for row in preview.eligible)
        message = (
            f"{preview.criteria.description}\n\n"
            f"Permanently delete {len(preview.eligible)} vouchers and {bars} associated silver bars?\n"
            f"Keep {len(preview.skipped)} protected vouchers.\n\n"
            "This cannot be undone."
        )
        warning = self.controller.entry_warning(preview)
        if warning:
            message += f"\n\n{warning}"
        return (
            QMessageBox.warning(
                self,
                "Confirm Voucher Deletion",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            == QMessageBox.StandardButton.Yes
        )

    def _delete(self):
        preview = self._preview
        if preview is None or not preview.eligible or not self._confirm(preview):
            return
        self.delete_button.setEnabled(False)
        try:
            result = self.controller.delete(preview, self)
        except Exception as exc:
            self._invalidate()
            QMessageBox.critical(self, "Deletion Failed", str(exc))
            return
        self._preview = None
        if not result.succeeded:
            self._invalidate()
            self.summary.setText(result.message)
            return
        self.model.replace(preview.rows, completed=True)
        self.summary.setText(
            f"Deleted: {len(result.deleted_vouchers)} • Skipped: {len(result.skipped)}. Kept vouchers and reasons are listed below."
            + (f"\n{result.message}" if result.message else "")
        )
