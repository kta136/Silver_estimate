"""History correctness and lifecycle checks using the real encrypted database."""

import threading
import time
from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PySide6.QtWidgets import QDialog, QMessageBox
from shiboken6 import isValid

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.ui.estimate_history import EstimateHistoryDialog
from silverestimate.ui.view_models import EstimateEntryRowState


@pytest.fixture
def history_db(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "history.db"), "test-pass", device_secret=b"H" * 32
    )
    for code in ("REG", "RET", "BAR"):
        assert db.add_item(code, code, 90, "WT", 10)
    yield db
    db.close()


def _draft(widget):
    widget.voucher_edit.setText("DRAFT")
    widget.note_edit.setText("Keep the draft")
    widget.item_table.replace_all_rows(
        [
            EstimateEntryRowState(
                code="REG",
                name="Regular",
                gross=10,
                net_weight=10,
                purity=90,
                fine_weight=9,
                wage_rate=10,
                wage_amount=100,
            ),
        ]
    )
    widget._set_unsaved(True, force=True)


@pytest.mark.parametrize(
    "balance_silver,balance_amount,rate", [(2, 50, 100), (-2, -50, 100), (2, -50, 0)]
)
def test_saved_entry_and_history_totals_include_both_balances(
    qtbot, history_db, make_estimate_widget, balance_silver, balance_amount, rate
):
    from silverestimate.services.estimate_entry_persistence import (
        EstimateEntryPersistenceService,
    )

    widget = make_estimate_widget(history_db)
    _draft(widget)
    regular = widget.item_table.get_all_rows()[0]
    widget.item_table.replace_all_rows(
        [
            regular,
            replace(
                regular,
                code="RET",
                line_key="return-line",
                category=EstimateLineCategory.RETURN,
                fine_weight=2,
                wage_amount=20,
            ),
            replace(
                regular,
                code="BAR",
                line_key="bar-line",
                category=EstimateLineCategory.SILVER_BAR,
                fine_weight=1,
                wage_amount=0,
            ),
        ]
    )
    widget.last_balance_silver = balance_silver
    widget.last_balance_amount = balance_amount
    widget.silver_rate_spin.setValue(rate)
    widget.workflow_controller._update_view_model_snapshot()
    service = EstimateEntryPersistenceService(widget.view_model.as_save_snapshot())
    outcome, _ = service.execute_save(
        voucher_no="1", date="2026-09-05", note="Balances", presenter=widget.presenter
    )
    assert outcome.success
    expected = ((6 + balance_silver) * rate if rate > 0 else 0) + 80 + balance_amount
    dialog = EstimateHistoryDialog(history_db, None)
    try:
        qtbot.waitUntil(lambda: dialog.estimates_model.rowCount() == 1)
        row = dialog.estimates_model.row_payload(0)
        assert row.grand_total == pytest.approx(expected)
        assert (
            history_db.get_estimate_history_rows()[0]["last_balance_silver"]
            == balance_silver
        )
        loaded = widget.presenter.load_estimate("1")
        assert widget.apply_loaded_estimate(loaded)
        widget.workflow_controller._update_view_model_snapshot()
        assert widget.view_model.compute_totals().grand_total == pytest.approx(expected)
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize(
    "choice,valid",
    [("Cancel", True), ("Discard", True), ("Save", True), ("Save", False)],
)
def test_history_choice_preserves_or_saves_draft_before_replacing(
    qtbot, history_db, make_estimate_widget, monkeypatch, choice, valid
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    if not valid:
        row = widget.item_table.get_all_rows()[0]
        widget.item_table.replace_all_rows([replace(row, poly=20)])
    before = widget.item_table.get_all_rows()
    assert history_db.save_estimate_with_returns(
        "TARGET", "2026-09-05", 75, [], [], {"note": "Target"}
    )
    monkeypatch.setattr(
        EstimateHistoryDialog,
        "exec",
        lambda dialog: (
            setattr(dialog, "selected_voucher", "TARGET") or QDialog.DialogCode.Accepted
        ),
    )
    prompts = []

    def choose(*args):
        prompts.append(args)
        return getattr(QMessageBox.StandardButton, choice)

    monkeypatch.setattr(QMessageBox, "question", choose)
    for method in ("information", "warning", "critical"):
        monkeypatch.setattr(
            QMessageBox, method, lambda *args: QMessageBox.StandardButton.Ok
        )
    print_calls = []
    monkeypatch.setattr(
        widget.workflow_controller, "print_estimate", lambda: print_calls.append(True)
    )

    widget.show_history()

    assert len(prompts) == 1
    if choice == "Cancel" or not valid:
        assert widget.note_edit.text() == "Keep the draft"
        assert widget.voucher_edit.text() == "DRAFT"
        assert widget.item_table.get_all_rows() == before
        assert widget.has_unsaved_changes()
    else:
        assert widget.note_edit.text() == "Target"
        assert widget.voucher_edit.text() == "TARGET"
        assert not widget.has_unsaved_changes()
    saved = history_db.get_estimate_by_voucher("DRAFT")
    assert bool(saved) == (choice == "Save" and valid)
    if saved:
        assert saved["header"]["note"] == "Keep the draft"
        assert len(saved["items"]) == 1
    assert not print_calls


@pytest.mark.parametrize("completion", ["accept", "reject", "close", "done"])
def test_fifty_history_cycles_release_dialogs_and_workers(
    qtbot, history_db, make_estimate_widget, completion
):
    widget = make_estimate_widget(history_db)
    assert history_db.save_estimate_with_returns("1", "2026-09-05", 75, [], [], {})
    seen = []
    timed_out = []
    deadline = 0.0

    def finish_when_loaded():
        dialogs = widget.findChildren(EstimateHistoryDialog)
        if time.monotonic() > deadline:
            timed_out.append(True)
            for dialog in dialogs:
                dialog.reject()
            return
        if not dialogs or not dialogs[-1].estimates_model.rowCount():
            QTimer.singleShot(1, finish_when_loaded)
            return
        dialog = dialogs[-1]
        seen.append(dialog)
        if completion == "done":
            dialog.done(QDialog.DialogCode.Rejected)
        else:
            getattr(dialog, completion)()

    try:
        for _ in range(50):
            deadline = time.monotonic() + 5
            QTimer.singleShot(0, finish_when_loaded)
            result = widget.workflow_controller.open_history_dialog()
            assert not timed_out, "History did not load before the cycle deadline"
            assert result == ("1" if completion == "accept" else None)
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert not widget.findChildren(EstimateHistoryDialog)
            assert not any(
                thread.name in {"estimate-history-loader", "print-preview-builder"}
                for thread in threading.enumerate()
            )
    finally:
        for dialog in seen:
            if isValid(dialog):
                dialog._load_runner.shutdown()
                if dialog._preview_builder._runner is not None:
                    dialog._preview_builder._runner.shutdown()
                dialog.close()
                dialog.deleteLater()


def test_history_preview_worker_starts_only_when_print_is_requested(qtbot, history_db):
    dialog = EstimateHistoryDialog(history_db, None)
    try:
        assert dialog._preview_builder._runner is None
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("action", ["open", "print", "delete"])
def test_sort_then_action_uses_the_originally_selected_voucher(
    qtbot, history_db, monkeypatch, action
):
    from types import SimpleNamespace

    from silverestimate.ui import estimate_history as history_module

    for voucher in ("1", "2", "10"):
        assert history_db.save_estimate_with_returns(
            voucher, "2026-09-05", 75, [], [], {"note": voucher}
        )
    dialog = EstimateHistoryDialog(history_db, None)
    monkeypatch.setattr(history_module, "confirm_estimate_deletion", lambda *_: True)
    printed = []
    monkeypatch.setattr(
        history_module,
        "PrintManager",
        lambda *args, **kwargs: SimpleNamespace(
            build_estimate_preview_payload=lambda voucher, **kwargs: printed.append(
                voucher
            )
        ),
    )
    monkeypatch.setattr(
        dialog, "_start_print_preview_build", lambda **kwargs: kwargs["build_preview"]()
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok
    )
    try:
        qtbot.waitUntil(lambda: dialog.estimates_model.rowCount() == 3)
        model = dialog.estimates_model
        row = next(i for i in range(3) if model.row_payload(i).voucher_no == "2")
        dialog.estimates_table.selectRow(row)
        dialog.estimates_table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        dialog.estimates_table.sortByColumn(0, Qt.SortOrder.DescendingOrder)
        assert dialog.get_selected_voucher() == "2"
        if action == "open":
            dialog.accept()
            assert dialog.selected_voucher == "2"
        elif action == "print":
            dialog.print_estimate()
            assert printed == ["2"]
        else:
            dialog.delete_selected_estimate()
            assert history_db.get_estimate_by_voucher("2") is None
            assert history_db.get_estimate_by_voucher("1")
            assert history_db.get_estimate_by_voucher("10")
    finally:
        dialog.close()
        dialog.deleteLater()


def test_appending_history_page_preserves_selected_voucher(qtbot, history_db):
    from silverestimate.domain.pagination import Page

    dialog = EstimateHistoryDialog(history_db, None)
    try:
        qtbot.waitUntil(lambda: dialog.search_button.isEnabled())
        dialog._populate_table(
            Page(({"voucher_no": "2"}, {"voucher_no": "1"}), 3, None)
        )
        model = dialog.estimates_model
        row = next(i for i in range(2) if model.row_payload(i).voucher_no == "1")
        dialog.estimates_table.selectRow(row)
        dialog._populate_table(Page(({"voucher_no": "10"},), 3, None), append=True)
        assert dialog.get_selected_voucher() == "1"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_closing_during_history_query_releases_reader_and_worker(
    qtbot, history_db, monkeypatch
):
    from silverestimate.infrastructure.sqlite_worker import (
        cancellable_sqlite_connection,
    )
    from silverestimate.ui import estimate_history as history_module

    started = threading.Event()
    closed = threading.Event()

    def slow_query(request, cancel_event):
        try:
            with cancellable_sqlite_connection(
                request.connection_factory, cancel_event
            ) as connection:
                started.set()
                connection.execute("""WITH RECURSIVE n(x) AS (
                    VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x < 100000000
                ) SELECT SUM(x) FROM n""").fetchone()
        finally:
            closed.set()

    monkeypatch.setattr(history_module, "_load_history_page", slow_query)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args))
    for _ in range(50):
        started.clear()
        closed.clear()
        dialog = EstimateHistoryDialog(history_db, None)
        try:
            assert started.wait(2)
            dialog.reject()
            assert closed.is_set()
            assert not dialog._load_runner._thread.is_alive()
            qtbot.wait(1)
            assert dialog.estimates_model.rowCount() == 0
            with history_db._broker.maintenance(timeout_seconds=0.1):
                pass
        finally:
            dialog.close()
            dialog.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not messages


def test_queued_preview_cannot_open_after_history_closes(
    qtbot, history_db, monkeypatch
):
    from types import SimpleNamespace

    dialog = EstimateHistoryDialog(history_db, None)
    queued = threading.Event()
    displayed = []
    manager = SimpleNamespace(
        show_preview=lambda *args, **kwargs: displayed.append(True)
    )
    try:
        # Start a blocking build so the listener is connected before it completes.
        release = threading.Event()

        def build():
            release.wait(2)
            return object()

        dialog._start_print_preview_build(print_manager=manager, build_preview=build)
        runner = dialog._preview_builder._runner
        runner.result.connect(
            lambda *args: queued.set(), Qt.ConnectionType.DirectConnection
        )
        release.set()
        assert queued.wait(2)
        dialog.reject()
        qtbot.wait(1)
        assert not displayed
        assert dialog._preview_builder._progress is None
        qtbot.waitUntil(lambda: not runner._thread.is_alive())
    finally:
        dialog.close()
        dialog.deleteLater()


@pytest.mark.parametrize("failure", ["database", "inventory"])
def test_history_save_failure_keeps_draft_and_rolls_back_header_and_inventory(
    qtbot, history_db, make_estimate_widget, monkeypatch, failure
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    bar = replace(
        widget.item_table.get_all_rows()[0],
        code="BAR",
        line_key="bar",
        category=EstimateLineCategory.SILVER_BAR,
    )
    widget.item_table.replace_all_rows([bar])
    rows_before = widget.item_table.get_all_rows()
    monkeypatch.setattr(
        EstimateHistoryDialog,
        "exec",
        lambda dialog: (
            setattr(dialog, "selected_voucher", "TARGET") or QDialog.DialogCode.Accepted
        ),
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Save
    )
    messages = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: messages.append(args[2]))
    if failure == "database":
        history_db.conn.execute("""CREATE TRIGGER fail_save BEFORE INSERT ON estimates
            BEGIN SELECT RAISE(ABORT, 'Injected save failure'); END""")
    else:
        history_db.conn.execute("""CREATE TRIGGER fail_save BEFORE INSERT ON silver_bars
            BEGIN SELECT RAISE(ABORT, 'Injected inventory failure'); END""")
    widget.show_history()
    assert widget.voucher_edit.text() == "DRAFT"
    assert widget.note_edit.text() == "Keep the draft"
    assert widget.has_unsaved_changes()
    assert widget.item_table.get_all_rows() == rows_before
    assert history_db.get_estimate_by_voucher("DRAFT") is None
    assert history_db.silver_bar_query_repo.get_silver_bars_for_estimate("DRAFT") == []
    assert messages


def test_inventory_failure_keeps_normal_save_draft_and_retry_commits_everything(
    qtbot, history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    widget.item_table.replace_all_rows(
        [
            replace(
                widget.item_table.get_all_rows()[0],
                code="BAR",
                line_key="bar",
                category=EstimateLineCategory.SILVER_BAR,
            )
        ]
    )
    rows_before = widget.item_table.get_all_rows()
    workflow = widget.workflow_controller
    printed, cleared, errors, successes = [], [], [], []
    monkeypatch.setattr(workflow, "print_estimate", lambda: printed.append(True))
    monkeypatch.setattr(workflow, "clear_form", lambda **kwargs: cleared.append(True))
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[2]))
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args: successes.append(args[2])
    )
    history_db.conn.execute("""CREATE TRIGGER fail_save BEFORE INSERT ON silver_bars
        BEGIN SELECT RAISE(ABORT, 'Injected inventory failure'); END""")
    assert workflow.save_estimate() is False
    assert errors and not printed and not cleared and not successes
    assert widget.voucher_edit.text() == "DRAFT"
    assert widget.note_edit.text() == "Keep the draft"
    assert widget.item_table.get_all_rows() == rows_before
    assert widget.has_unsaved_changes()
    assert history_db.get_estimate_by_voucher("DRAFT") is None
    history_db.conn.execute("DROP TRIGGER fail_save")
    assert workflow.save_estimate() is True
    assert printed == cleared == [True]
    assert len(successes) == 1
    saved = history_db.get_estimate_by_voucher("DRAFT")
    bars = history_db.silver_bar_query_repo.get_silver_bars_for_estimate("DRAFT")
    assert len(bars) == 1
    assert bars[0]["source_line_key"] == saved["items"][0]["line_key"]
    assert bars[0]["weight"] == saved["items"][0]["net_wt"]


def test_canceling_history_does_not_prompt_to_replace_the_draft(
    qtbot, history_db, make_estimate_widget, monkeypatch
):
    widget = make_estimate_widget(history_db)
    _draft(widget)
    monkeypatch.setattr(
        EstimateHistoryDialog, "exec", lambda dialog: QDialog.DialogCode.Rejected
    )
    prompts = []
    monkeypatch.setattr(QMessageBox, "question", lambda *args: prompts.append(args))
    widget.show_history()
    assert not prompts
    assert widget.voucher_edit.text() == "DRAFT"
    assert widget.has_unsaved_changes()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert not widget.findChildren(EstimateHistoryDialog)
