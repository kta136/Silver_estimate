"""Coordinate reviewed deletion with worker connections and the active entry."""

from __future__ import annotations

import logging
from dataclasses import replace

from silverestimate.domain.voucher_deletion import (
    VoucherDeletionPreview,
    VoucherDeletionRange,
    VoucherDeletionResult,
)
from silverestimate.persistence.database_protocols import MainCommandsDatabase
from silverestimate.persistence.voucher_deletion_repository import (
    fetch_voucher_deletion_preview,
)
from silverestimate.ui.database_maintenance import run_database_maintenance
from silverestimate.ui.maintenance_progress import MaintenanceProgressDialog


class VoucherDeletionController:
    def __init__(self, database: MainCommandsDatabase, main_window) -> None:
        self.database = database
        self.main_window = main_window

    def preview(self, criteria: VoucherDeletionRange, parent) -> VoucherDeletionPreview:
        connection_factory = self.database.open_read_connection

        def read() -> VoucherDeletionPreview:
            with connection_factory() as conn:
                conn.execute("BEGIN")
                try:
                    return fetch_voucher_deletion_preview(conn.cursor(), criteria)
                finally:
                    conn.rollback()

        dialog = MaintenanceProgressDialog(read, "Previewing Vouchers", parent)
        try:
            result = dialog.run_operation()
            if not isinstance(result, VoucherDeletionPreview):
                raise RuntimeError("Could not read the voucher preview.")
            return result
        finally:
            dialog.deleteLater()

    def _entry_is_affected(self, vouchers: set[str]) -> bool:
        entry = getattr(self.main_window, "estimate_widget", None)
        if entry is None:
            return False
        # The edit box can contain a not-yet-loaded number. The active identity
        # still owns this entry, just as it does during save-before-navigation.
        identity = str(getattr(entry, "_active_voucher_no", "") or "").strip()
        return (identity or entry.voucher_edit.text().strip()) in vouchers

    def entry_warning(self, preview: VoucherDeletionPreview) -> str:
        if self._entry_is_affected({row.voucher_no for row in preview.eligible}):
            return (
                "The current entry will also be cleared, including any unsaved edits."
            )
        return ""

    def delete(self, preview: VoucherDeletionPreview, parent) -> VoucherDeletionResult:
        result = run_database_maintenance(
            self.database,
            lambda worker: worker.delete_voucher_range(preview),
            "Deleting Vouchers",
            parent,
        )
        if result.succeeded:
            try:
                self._refresh_after_deletion(result)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Vouchers deleted, but view refresh failed"
                )
                return replace(
                    result,
                    message="Deletion completed, but the open views could not refresh. Reopen the application before continuing.",
                )
        return result

    def _refresh_after_deletion(self, result: VoucherDeletionResult) -> None:
        entry = getattr(self.main_window, "estimate_widget", None)
        if entry is not None:
            recovery = getattr(entry, "draft_recovery", None)
            if recovery is not None and result.deleted_draft_token:
                recovery.forget_deleted_draft(result.deleted_draft_token)
            if self._entry_is_affected(set(result.deleted_vouchers)):
                entry.clear_form(confirm=False)
        report = getattr(self.main_window, "sales_report_widget", None)
        if report is not None and report.isVisible():
            report.refresh()
