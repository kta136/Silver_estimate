"""Review a date or numeric voucher range before deleting eligible records."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
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
from silverestimate.ui.display_formatting import count_label, format_display_date
from silverestimate.ui.message_dialogs import confirm_destructive, with_details
from silverestimate.ui.modern_components import (
    install_table_empty_state,
    polish_dense_table,
)
from silverestimate.ui.screen_widgets import SCREEN_QSS, OptionGroup
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.themed_controls import ThemedDateEdit

_DELETE_LABEL = "Delete Vouchers..."


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
        return (row.voucher_no, format_display_date(row.date), status)[index.column()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return ("Voucher", "Date", "Result")[section]
        return None


class VoucherRangeDeletionDialog(QDialog):
    def __init__(  # noqa: PLR0915 - declarative dialog layout
        self, controller: VoucherDeletionController, parent=None
    ):
        super().__init__(parent)
        self.controller = controller
        self._preview: VoucherDeletionPreview | None = None
        self.setWindowTitle("Delete Vouchers by Range")
        self.setObjectName("VoucherRangeDialog")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#VoucherRangeDialog",
                card_names=["VoucherRangeCard"],
                title_label="VoucherRangeTitle",
                subtitle_label="VoucherRangeSubtitle",
                field_label="VoucherRangeFieldLabel",
                primary_button="VoucherRangePrimaryButton",
                secondary_button="VoucherRangeSecondaryButton",
                danger_button="SettingsDangerButton",
                input_selectors=["QLineEdit", "QDateEdit"],
                include_table=True,
                extra_rules=SCREEN_QSS
                + """
                QLabel#VoucherRangeFieldLabel[problem="true"] {
                    color: #b91c1c;
                }
                """,
            )
        )
        self.resize(820, 560)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title = QLabel("Delete Vouchers by Range")
        title.setObjectName("VoucherRangeTitle")
        layout.addWidget(title)
        explanation = QLabel(
            "Choose a range and preview it before anything is deleted. Both ends "
            "of the range are included, and dates are the saved estimate dates. "
            "Vouchers with assigned, issued or transferred silver bars are kept."
        )
        explanation.setObjectName("VoucherRangeSubtitle")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        card = QFrame(self)
        card.setObjectName("VoucherRangeCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(14)
        self.mode = OptionGroup("segmented", card)
        self.mode.addItem("Date range")
        self.mode.addItem("Voucher numbers")
        self.mode.setAccessibleName("Range type")
        card_layout.addWidget(self.mode, 0, Qt.AlignmentFlag.AlignVCenter)

        self.fields = QStackedWidget()
        self.fields.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        dates, numbers = QWidget(), QWidget()
        self.date_from, self.date_to = (
            ThemedDateEdit(QDate.currentDate()),
            ThemedDateEdit(QDate.currentDate()),
        )
        for field in (self.date_from, self.date_to):
            field.setCalendarPopup(True)
            field.setDisplayFormat("dd/MM/yyyy")
            field.setMinimumWidth(130)
            field.dateChanged.connect(self._invalidate)
        self.voucher_from, self.voucher_to = QLineEdit(), QLineEdit()
        for number_field in (self.voucher_from, self.voucher_to):
            number_field.setPlaceholderText("Voucher number")
            number_field.setMinimumWidth(130)
            number_field.textChanged.connect(self._invalidate)
        for page, first, last in (
            (dates, self.date_from, self.date_to),
            (numbers, self.voucher_from, self.voucher_to),
        ):
            row = QHBoxLayout(page)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            form.addRow("From", first)
            row.addLayout(form)
            second = QFormLayout()
            second.setContentsMargins(0, 0, 0, 0)
            second.addRow("To", last)
            row.addLayout(second)
            row.addStretch(1)
        self.fields.addWidget(dates)
        self.fields.addWidget(numbers)
        card_layout.addWidget(self.fields, 1)
        self.mode.currentIndexChanged.connect(self.fields.setCurrentIndex)
        self.mode.currentIndexChanged.connect(self._invalidate)

        self.preview_button = QPushButton("Preview")
        self.preview_button.setObjectName("VoucherRangePrimaryButton")
        self.preview_button.setToolTip("List the vouchers in this range")
        self.preview_button.clicked.connect(self._load_preview)
        card_layout.addWidget(self.preview_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(card)
        self._build_results(layout)

    def _build_results(self, layout: QVBoxLayout) -> None:
        self.summary = QLabel("Choose a range, then preview the matching vouchers.")
        self.summary.setObjectName("VoucherRangeFieldLabel")
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
        polish_dense_table(
            self.table,
            row_height=28,
            header_height=30,
            show_grid=False,
            hide_vertical_header=True,
        )
        self.table.setAlternatingRowColors(True)
        install_table_empty_state(self.table, "Preview a range to list its vouchers.")
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.delete_button = QPushButton(_DELETE_LABEL)
        self.delete_button.setObjectName("SettingsDangerButton")
        self.delete_button.setEnabled(False)
        self.delete_button.setAutoDefault(False)
        self.delete_button.clicked.connect(self._delete)
        footer.addWidget(self.delete_button)
        footer.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("VoucherRangeSecondaryButton")
        self.close_button.setAutoDefault(False)
        self.close_button.clicked.connect(self.reject)
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

    def _say(self, text: str, *, problem: bool = False) -> None:
        """Show one line above the table; red when it asks for a correction."""
        self.summary.setText(text)
        if bool(self.summary.property("problem")) != problem:
            self.summary.setProperty("problem", problem)
            style = self.summary.style()
            style.unpolish(self.summary)
            style.polish(self.summary)

    def _invalidate(self, *_args):
        self._preview = None
        self.delete_button.setEnabled(False)
        self.delete_button.setText(_DELETE_LABEL)
        self.model.replace(())
        self._say("Range changed. Preview the matching vouchers again.")

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
        # What is missing or wrong is said in the dialog, beside the
        # fields, not in a box the user has to dismiss first.
        if self.mode.currentIndex() == 1:
            for field in (self.voucher_from, self.voucher_to):
                if not field.text().strip():
                    self._say(
                        "Enter the first and the last voucher number.", problem=True
                    )
                    field.setFocus()
                    return
        try:
            preview = self.controller.preview(self._criteria(), self)
        except ValueError as exc:
            self._say(str(exc), problem=True)
            return
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Vouchers Not Listed",
                with_details("The vouchers in this range could not be listed.", exc),
            )
            return
        self._preview = preview
        self.model.replace(preview.rows)
        eligible = len(preview.eligible)
        self._say(
            f"Matched: {len(preview.rows)} · Eligible: {eligible} · "
            f"Protected: {len(preview.skipped)}"
        )
        self.delete_button.setEnabled(bool(preview.eligible))
        if eligible:
            self.delete_button.setText(f"Delete {count_label(eligible, 'Voucher')}...")

    def _confirm(self, preview: VoucherDeletionPreview) -> bool:
        bars = sum(row.bar_count for row in preview.eligible)
        vouchers = count_label(len(preview.eligible), "voucher")
        detail = (
            f"{self._range_text(preview.criteria)}\n\n"
            f"{vouchers} and {count_label(bars, 'silver bar')} will be removed. "
            f"{count_label(len(preview.skipped), 'protected voucher')} will be kept.\n\n"
            "This cannot be undone. Back up the database first if you may need "
            "this data."
        )
        warning = self.controller.entry_warning(preview)
        if warning:
            detail += f"\n\n{warning}"
        return confirm_destructive(
            self,
            title="Delete Vouchers",
            heading=f"Permanently delete {vouchers}?",
            detail=detail,
            action_label=f"Delete {count_label(len(preview.eligible), 'Voucher')}",
        )

    @staticmethod
    def _range_text(criteria: VoucherDeletionRange) -> str:
        """The chosen range, with dates written as they are on screen."""
        if criteria.mode == "date":
            return (
                f"Dates {format_display_date(criteria.start)} to "
                f"{format_display_date(criteria.end)}, both included"
            )
        return f"Vouchers {criteria.start} to {criteria.end}, both included"

    def _delete(self):
        preview = self._preview
        if preview is None or not preview.eligible or not self._confirm(preview):
            return
        self.delete_button.setEnabled(False)
        try:
            result = self.controller.delete(preview, self)
        except Exception as exc:
            self._invalidate()
            QMessageBox.critical(
                self,
                "Vouchers Not Deleted",
                with_details("The vouchers could not be deleted.", exc),
            )
            return
        self._preview = None
        if not result.succeeded:
            self._invalidate()
            self._say(result.message, problem=True)
            return
        self.model.replace(preview.rows, completed=True)
        self.delete_button.setText(_DELETE_LABEL)
        self._say(
            f"Deleted: {len(result.deleted_vouchers)} · Skipped: {len(result.skipped)}. Kept vouchers and reasons are listed below."
            + (f"\n{result.message}" if result.message else "")
        )
