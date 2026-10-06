"""Range dialog, confirmation, encrypted workers, and active draft lifecycle."""

import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QMessageBox

from silverestimate.domain.voucher_deletion import (
    VoucherDeletionPreview,
    VoucherDeletionRange,
    VoucherDeletionResult,
    VoucherDeletionRow,
)
from silverestimate.services import voucher_deletion as service
from silverestimate.services.voucher_deletion import VoucherDeletionController
from silverestimate.ui.voucher_range_deletion_dialog import VoucherRangeDeletionDialog
from tests.integration.test_voucher_range_deletion import bar, voucher
from tests.ui.test_history_safeguards import _draft, history_db

__all__ = ["history_db"]


class Controller:
    def __init__(self):
        self.rows = (
            VoucherDeletionRow("1", "2026-10-04", 2),
            VoucherDeletionRow("2", "2026-10-04", 1, "Assigned silver bar"),
        )
        self.previews, self.deletions = [], []
        self.result = VoucherDeletionResult(True, ("1",), (self.rows[1],))

    def preview(self, criteria, parent):
        self.previews.append(criteria)
        return VoucherDeletionPreview(criteria, self.rows, "snapshot")

    def entry_warning(self, preview):
        return "The current entry will also be cleared, including any unsaved edits."

    def delete(self, preview, parent):
        self.deletions.append(preview)
        return self.result


@pytest.fixture
def dialog(qtbot):
    view = VoucherRangeDeletionDialog(Controller())
    qtbot.addWidget(view)
    return view


def test_defaults_preview_confirmation_and_result(dialog, monkeypatch):
    assert dialog.date_from.date() == dialog.date_to.date() == QDate.currentDate()
    assert not dialog.voucher_from.text() and not dialog.voucher_to.text()
    assert not dialog.delete_button.isEnabled()
    dialog.preview_button.click()
    assert dialog.model.rowCount() == 2
    assert "Eligible: 1" in dialog.summary.text()
    confirmations = []

    def confirm(*args):
        confirmations.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "warning", confirm)
    dialog.delete_button.click()
    message = confirmations[0][2]
    assert "1 vouchers and 2 associated silver bars" in message
    assert "Keep 1 protected" in message and "unsaved edits" in message
    assert confirmations[0][-1] == QMessageBox.StandardButton.Cancel
    assert len(dialog.controller.deletions) == 1
    assert (
        "Deleted: 1" in dialog.summary.text() and "Skipped: 1" in dialog.summary.text()
    )
    assert dialog.model.data(dialog.model.index(1, 2)) == "Kept: Assigned silver bar"
    assert dialog.model.data(dialog.model.index(0, 2)) == "Deleted"
    assert not dialog.delete_button.isEnabled()


def test_cancel_does_not_delete_or_invalidate_review(dialog, monkeypatch):
    dialog.preview_button.click()
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: QMessageBox.StandardButton.Cancel
    )
    dialog.delete_button.click()
    assert not dialog.controller.deletions
    assert dialog.delete_button.isEnabled()
    dialog.reject()
    assert not dialog.controller.deletions


@pytest.mark.parametrize(
    "field", ["date_from", "date_to", "mode", "voucher_from", "voucher_to"]
)
def test_changing_any_range_control_invalidates_preview(dialog, field):
    dialog.preview_button.click()
    if field.startswith("date"):
        getattr(dialog, field).setDate(QDate.currentDate().addDays(1))
    elif field == "mode":
        dialog.mode.setCurrentIndex(1)
    else:
        getattr(dialog, field).setText("10")
    assert dialog._preview is None and not dialog.delete_button.isEnabled()
    assert dialog.model.rowCount() == 0


def test_numeric_validation_and_preview(dialog, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a))
    dialog.mode.setCurrentIndex(1)
    dialog.preview_button.click()
    assert warnings and not dialog.controller.previews
    dialog.voucher_from.setText("00010")
    dialog.voucher_to.setText("2")
    dialog.preview_button.click()
    assert len(warnings) == 2 and not dialog.controller.previews
    dialog.voucher_to.setText("10")
    dialog.preview_button.click()
    assert dialog.controller.previews == [
        VoucherDeletionRange("voucher", "00010", "10")
    ]


@pytest.mark.parametrize(
    "rows", [(), (VoucherDeletionRow("2", "2026-10-04", 1, "Issued"),)]
)
def test_empty_or_all_protected_preview_cannot_delete(dialog, rows):
    dialog.controller.rows = rows
    dialog.preview_button.click()
    assert not dialog.delete_button.isEnabled()
    assert dialog.model.rowCount() == len(rows)


def test_stale_preview_requires_preview_again(dialog, monkeypatch):
    dialog.controller.result = VoucherDeletionResult(
        False, stale=True, message="Preview again"
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: QMessageBox.StandardButton.Yes
    )
    dialog.preview_button.click()
    dialog.delete_button.click()
    assert dialog._preview is None and not dialog.delete_button.isEnabled()
    assert dialog.summary.text() == "Preview again"


def test_deletion_error_is_visible_and_not_retryable_without_review(
    dialog, monkeypatch
):
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a: QMessageBox.StandardButton.Yes
    )
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a: errors.append(a))

    def fail(*args):
        raise RuntimeError("Database failure")

    dialog.controller.delete = fail
    dialog.preview_button.click()
    dialog.delete_button.click()
    assert "Database failure" in errors[0][2]
    assert not dialog.delete_button.isEnabled() and dialog._preview is None


def test_settings_range_button_uses_injected_command(qtbot):
    from silverestimate.ui.settings_data_page import (
        DataManagementActions,
        DataManagementPage,
        SettingsDataController,
    )

    calls = []
    actions = DataManagementActions(
        *(lambda: None for _ in range(4)),
        delete_vouchers_by_range=lambda: calls.append(True),
    )
    page = DataManagementPage(SettingsDataController(lambda: None, actions))
    qtbot.addWidget(page)
    page.delete_range_button.click()
    assert calls == [True]


def test_real_preview_and_deletion_use_worker_connections(
    qtbot, history_db, monkeypatch
):
    voucher(history_db, "1")
    voucher(history_db, "2")
    bar(history_db, "2", "Issued")
    owner = threading.get_ident()
    reads, writes = [], []
    original_read = service.fetch_voucher_deletion_preview

    def read(cursor, criteria):
        reads.append(threading.get_ident())
        return original_read(cursor, criteria)

    monkeypatch.setattr(service, "fetch_voucher_deletion_preview", read)
    original_delete = type(history_db).delete_voucher_range

    def delete(worker, selected):
        writes.append((threading.get_ident(), worker is history_db))
        return original_delete(worker, selected)

    monkeypatch.setattr(type(history_db), "delete_voucher_range", delete)
    refreshed = []
    host = SimpleNamespace(
        sales_report_widget=SimpleNamespace(
            isVisible=lambda: True, refresh=lambda: refreshed.append(True)
        )
    )
    controller = VoucherDeletionController(history_db, host)
    selected = controller.preview(VoucherDeletionRange("voucher", "1", "2"), None)
    result = controller.delete(selected, None)
    assert result.deleted_vouchers == ("1",) and result.skipped[0].voucher_no == "2"
    assert reads and all(t != owner for t in reads)
    assert writes and all(t != owner and not original for t, original in writes)
    assert history_db._session.is_owner() and not history_db._broker.maintenance_active
    assert history_db.get_estimate_by_voucher("1") is None
    assert history_db.get_estimate_by_voucher("2") is not None
    assert refreshed == [True]


@pytest.mark.parametrize(
    "state",
    [
        "deleted",
        "protected",
        "unrelated",
        "renamed",
        "failure",
        "stale",
        "unrelated_renamed",
        "protected_renamed",
    ],
)
def test_real_active_entry_and_recovery_only_clear_after_committed_deletion(
    qtbot, history_db, make_estimate_widget, state
):
    voucher(history_db, "1")
    widget = make_estimate_widget(history_db)
    _draft(widget)
    active = (
        "3" if state in ("unrelated", "unrelated_renamed", "protected_renamed") else "1"
    )
    widget.set_voucher_number(active)
    if state == "renamed":
        widget.voucher_edit.setText("EDITED")
    if state in ("unrelated_renamed", "protected_renamed"):
        widget.voucher_edit.setText("1")
    if state == "protected_renamed":
        voucher(history_db, "3")
        bar(history_db, "3", "Issued")
    if state == "protected":
        bar(history_db, "1", "Issued")
    assert widget.draft_recovery.flush()
    token = history_db.draft_repository.load().token
    controller = VoucherDeletionController(
        history_db, SimpleNamespace(estimate_widget=widget)
    )
    selected = controller.preview(VoucherDeletionRange("voucher", "1", "3"), None)
    assert bool(controller.entry_warning(selected)) is (
        state
        not in ("protected", "unrelated", "unrelated_renamed", "protected_renamed")
    )
    if state == "failure":
        history_db.conn.execute(
            "CREATE TRIGGER reject_delete BEFORE DELETE ON estimates BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
        with pytest.raises(Exception, match="injected"):
            controller.delete(selected, None)
    else:
        if state == "stale":
            history_db.conn.execute("UPDATE estimates SET note='Changed'")
            history_db.conn.commit()
        result = controller.delete(selected, None)
        assert result.stale is (state == "stale")
    assert history_db._session.is_owner() and not history_db._broker.maintenance_active
    if state in ("deleted", "renamed"):
        assert not widget.has_unsaved_changes()
        assert widget.note_edit.text() == ""
        assert history_db.draft_repository.load() is None
        assert widget.draft_recovery._token is None
        assert not widget.draft_recovery.flush()
    else:
        assert widget.has_unsaved_changes()
        assert widget.note_edit.text() == "Keep the draft"
        assert history_db.draft_repository.load().token == token


def test_preview_failure_releases_reader(qtbot, history_db, monkeypatch):
    def fail(*args):
        raise RuntimeError("Preview failed")

    monkeypatch.setattr(service, "fetch_voucher_deletion_preview", fail)
    controller = VoucherDeletionController(history_db, SimpleNamespace())
    with pytest.raises(RuntimeError, match="Preview failed"):
        controller.preview(VoucherDeletionRange("voucher", "1", "2"), None)
    job = history_db.create_maintenance_job()
    try:
        history_db._broker.drain_readers(timeout_seconds=0.1)
    finally:
        job.resume_owner()


def test_postcommit_view_error_reports_deletion_as_completed(qtbot, history_db):
    voucher(history_db, "1")

    def fail():
        raise RuntimeError("Refresh failed")

    host = SimpleNamespace(
        sales_report_widget=SimpleNamespace(isVisible=lambda: True, refresh=fail)
    )
    controller = VoucherDeletionController(history_db, host)
    selected = controller.preview(VoucherDeletionRange("voucher", "1", "1"), None)
    result = controller.delete(selected, None)
    assert result.succeeded and result.deleted_vouchers == ("1",)
    assert "Deletion completed" in result.message
    assert history_db.get_estimate_by_voucher("1") is None


def test_main_command_opens_and_disposes_range_dialog(qtbot, monkeypatch):
    from PySide6.QtWidgets import QWidget

    from silverestimate.services.main_commands import MainCommands
    from silverestimate.ui import voucher_range_deletion_dialog as module

    calls = []

    class Dialog:
        def __init__(self, controller, parent):
            calls.append((controller, parent))

        def exec(self):
            calls.append("opened")

        def deleteLater(self):
            calls.append("disposed")

    host = QWidget()
    qtbot.addWidget(host)
    database = object()
    monkeypatch.setattr(module, "VoucherRangeDeletionDialog", Dialog)
    assert MainCommands(host, database).delete_vouchers_by_range().succeeded
    assert calls[0][0].database is database
    assert calls[0][0].main_window is calls[0][1] is host
    assert calls[1:] == ["opened", "disposed"]
