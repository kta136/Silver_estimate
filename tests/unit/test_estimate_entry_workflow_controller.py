from __future__ import annotations

import logging
import types
from typing import Any

import pytest
from PyQt5.QtCore import QDate, QObject, pyqtSignal
from PyQt5.QtWidgets import QDateEdit, QDialog, QDoubleSpinBox, QLabel, QLineEdit, QPushButton, QWidget

from silverestimate.presenter import LoadedEstimate, SaveItem, SaveOutcome
from silverestimate.ui import estimate_entry_workflow_controller as workflow_module
from silverestimate.ui.estimate_entry_workflow_controller import (
    EstimateEntryWorkflowController,
    _EstimatePreviewBuildWorker,
)
from silverestimate.ui.view_models import EstimateEntryRowState, EstimateEntryViewModel


class _MessageBoxStub:
    Yes = 1
    No = 2
    Cancel = 3

    question_return = Yes
    warning_calls: list[tuple[Any, ...]] = []
    information_calls: list[tuple[Any, ...]] = []
    critical_calls: list[tuple[Any, ...]] = []
    question_calls: list[tuple[Any, ...]] = []

    @classmethod
    def reset(cls) -> None:
        cls.question_return = cls.Yes
        cls.warning_calls = []
        cls.information_calls = []
        cls.critical_calls = []
        cls.question_calls = []

    @classmethod
    def warning(cls, *args):
        cls.warning_calls.append(args)
        return cls.Yes

    @classmethod
    def information(cls, *args):
        cls.information_calls.append(args)
        return cls.Yes

    @classmethod
    def critical(cls, *args):
        cls.critical_calls.append(args)
        return cls.Yes

    @classmethod
    def question(cls, *args):
        cls.question_calls.append(args)
        return cls.question_return


class _ItemTableStub:
    def __init__(self) -> None:
        self._row_count = 2
        self._current_row = 0
        self.block_calls: list[bool] = []
        self.deleted_rows: list[int] = []
        self.current_cells: list[tuple[int, int]] = []
        self.replaced_rows: list[Any] = []
        self.text_cells: dict[tuple[int, int], str] = {}

    def blockSignals(self, value: bool) -> None:
        self.block_calls.append(value)

    def rowCount(self) -> int:
        return self._row_count

    def currentRow(self) -> int:
        return self._current_row

    def delete_row(self, row: int) -> None:
        self.deleted_rows.append(row)
        self._row_count -= 1

    def setCurrentCell(self, row: int, col: int) -> None:
        self.current_cells.append((row, col))

    def replace_all_rows(self, rows) -> None:
        self.replaced_rows = list(rows)
        self._row_count = len(self.replaced_rows)

    def get_all_rows(self):
        return ()

    def get_cell_text(self, row: int, col: int) -> str:
        return self.text_cells.get((row, col), "")


class _AdapterStub:
    def __init__(self) -> None:
        self.refreshed = 0
        self.focus_calls: list[bool] = []

    def refresh_empty_row_type(self) -> None:
        self.refreshed += 1

    def focus_on_empty_row(self, *, update_visuals: bool = False) -> None:
        self.focus_calls.append(update_visuals)


class _ProgressStub:
    def __init__(self) -> None:
        self.closed = 0
        self.deleted = 0

    def close(self) -> None:
        self.closed += 1

    def deleteLater(self) -> None:
        self.deleted += 1


class _ThreadStub:
    def __init__(self) -> None:
        self.quit_calls = 0
        self.wait_calls: list[int] = []
        self.deleted = 0

    def quit(self) -> None:
        self.quit_calls += 1

    def wait(self, timeout: int) -> None:
        self.wait_calls.append(timeout)

    def deleteLater(self) -> None:
        self.deleted += 1


class _WorkerDisposeStub:
    def __init__(self) -> None:
        self.deleted = 0

    def deleteLater(self) -> None:
        self.deleted += 1


class _SignalStub:
    def __init__(self) -> None:
        self.emitted: list[Any] = []

    def emit(self, value) -> None:
        self.emitted.append(value)


class _ReturnSignalStub:
    def __init__(self) -> None:
        self.connected: list[Any] = []
        self.disconnected: list[Any] = []

    def connect(self, callback) -> None:
        self.connected.append(callback)

    def disconnect(self, callback) -> None:
        self.disconnected.append(callback)


class _VoucherEditStub(QObject):
    returnPressed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._text = ""

    def text(self) -> str:
        return self._text

    def setText(self, value: str) -> None:
        self._text = value

    def clear(self) -> None:
        self._text = ""


class _Host(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger("test.workflow")
        self.presenter = None
        self.main_window = types.SimpleNamespace(print_font=None)
        self.db_manager = object()
        self.view_model = EstimateEntryViewModel()
        self.initializing = False
        self._loading_estimate = False
        self._estimate_loaded = False
        self._unsaved_changes = False
        self._unsaved_block = 0
        self.processing_cell = False
        self.return_mode = False
        self.silver_bar_mode = False
        self.last_balance_silver = 0.0
        self.last_balance_amount = 0.0
        self._print_preview_request_id = 0
        self._active_print_preview_workers: dict[Any, Any] = {}

        self.voucher_edit = _VoucherEditStub()
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate(2026, 3, 20))
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setValue(0.0)
        self.note_edit = QLineEdit()
        self.delete_estimate_button = QPushButton()
        self.return_toggle_button = QPushButton()
        self.return_toggle_button.setCheckable(True)
        self.silver_bar_toggle_button = QPushButton()
        self.silver_bar_toggle_button.setCheckable(True)
        self.mode_indicator_label = QLabel()
        self.live_rate_value_label = QLabel()
        self.refresh_rate_button = QPushButton()
        self.refresh_rate_button.setEnabled(True)
        self.item_table = _ItemTableStub()
        self.live_rate_fetched = _SignalStub()

        self._adapter = _AdapterStub()
        self.status_calls: list[tuple[str, int]] = []
        self.focus_calls: list[int] = []
        self.mode_tooltip_updates = 0
        self.mark_unsaved_calls = 0
        self.schedule_totals_calls = 0
        self.schedule_columns_calls: list[bool] = []
        self.clear_rows_calls = 0
        self.add_row_calls = 0
        self.calculate_totals_calls = 0
        self.log_perf_calls: list[tuple[str, int]] = []

    def _status(self, message: str, timeout: int = 3000) -> None:
        self.status_calls.append((message, timeout))

    def has_unsaved_changes(self) -> bool:
        return self._unsaved_changes

    def _push_unsaved_block(self) -> None:
        self._unsaved_block += 1

    def _pop_unsaved_block(self) -> None:
        self._unsaved_block -= 1

    def _set_unsaved(self, dirty: bool, *, force: bool = False) -> None:
        del force
        self._unsaved_changes = dirty

    def focus_on_code_column(self, row: int) -> None:
        self.focus_calls.append(row)

    def clear_all_rows(self) -> None:
        self.clear_rows_calls += 1
        self.item_table._row_count = 0

    def add_empty_row(self) -> None:
        self.add_row_calls += 1
        self.item_table._row_count += 1

    def calculate_totals(self) -> None:
        self.calculate_totals_calls += 1

    def _get_table_adapter(self) -> _AdapterStub:
        return self._adapter

    def focus_on_empty_row(self, update_visuals: bool = False) -> None:
        self._adapter.focus_on_empty_row(update_visuals=update_visuals)

    def _update_mode_tooltip(self) -> None:
        self.mode_tooltip_updates += 1

    def _mark_unsaved(self) -> None:
        self.mark_unsaved_calls += 1

    def _schedule_totals_recalc(self) -> None:
        self.schedule_totals_calls += 1

    def _schedule_columns_autofit(self, *, force: bool = False) -> None:
        self.schedule_columns_calls.append(force)

    def _normalize_wage_type(self, value: object) -> str:
        return "PC" if str(value or "").strip().upper() == "PC" else "WT"

    def set_voucher_number(self, voucher_no: str) -> None:
        self.voucher_edit.setText(voucher_no)

    def _log_perf_metric(self, name: str, _start: float, **kwargs) -> None:
        self.log_perf_calls.append((name, int(kwargs.get("rows", 0))))


@pytest.fixture
def workflow_host(qt_app, monkeypatch):  # noqa: ARG001
    _MessageBoxStub.reset()
    monkeypatch.setattr(workflow_module, "QMessageBox", _MessageBoxStub)
    monkeypatch.setattr(
        workflow_module.refresh_widget_style,
        "__call__",
        getattr(workflow_module.refresh_widget_style, "__call__", None),
        raising=False,
    )
    monkeypatch.setattr(workflow_module, "refresh_widget_style", lambda *_a, **_k: None)
    host = _Host()
    controller = EstimateEntryWorkflowController(host)
    yield host, controller
    host.deleteLater()


def test_preview_worker_emits_payload_and_finished():
    ready = []
    finished = []
    worker = _EstimatePreviewBuildWorker(4, lambda: {"ok": True})
    worker.preview_ready.connect(lambda request_id, payload: ready.append((request_id, payload)))
    worker.finished.connect(lambda request_id: finished.append(request_id))

    worker.run()

    assert ready == [(4, {"ok": True})]
    assert finished == [4]


def test_preview_worker_emits_error_and_finished():
    errors = []
    finished = []
    worker = _EstimatePreviewBuildWorker(7, lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    worker.preview_error.connect(lambda request_id, message: errors.append((request_id, message)))
    worker.finished.connect(lambda request_id: finished.append(request_id))

    worker.run()

    assert errors == [(7, "boom")]
    assert finished == [7]


def test_format_currency_falls_back_for_bad_locale(workflow_host, monkeypatch):
    _host, controller = workflow_host

    class _BadLocale:
        def toCurrencyString(self, value):
            del value
            raise RuntimeError("bad locale")

    monkeypatch.setattr(workflow_module.QLocale, "system", lambda: _BadLocale())

    assert controller._format_currency("oops") == "oops"
    assert controller._format_currency(1234.4) == "₹ 1,234"


def test_generate_voucher_delegates_and_resets_loaded_state(workflow_host):
    host, controller = workflow_host
    calls = []
    host.presenter = types.SimpleNamespace(generate_voucher=lambda: calls.append("generate"))
    host._estimate_loaded = True
    host.delete_estimate_button.setEnabled(True)

    controller.generate_voucher()

    assert calls == ["generate"]
    assert host._estimate_loaded is False
    assert host.delete_estimate_button.isEnabled() is False


def test_load_estimate_success_reports_status_and_enables_delete(workflow_host, monkeypatch):
    host, controller = workflow_host
    loaded = object()
    host.voucher_edit.setText("V101")
    host.presenter = types.SimpleNamespace(load_estimate=lambda voucher_no: loaded)
    monkeypatch.setattr(
        workflow_module.EstimateEntryWorkflowController,
        "apply_loaded_estimate",
        lambda self, value: value is loaded,
    )

    controller.load_estimate()

    assert host.status_calls[0] == ("Loading estimate V101...", 2000)
    assert host.status_calls[-1] == ("Estimate V101 loaded successfully.", 3000)


def test_load_estimate_not_found_starts_new_entry(workflow_host):
    host, controller = workflow_host
    host.voucher_edit.setText("MISS1")
    host.presenter = types.SimpleNamespace(load_estimate=lambda voucher_no: None)
    host.delete_estimate_button.setEnabled(True)

    controller.load_estimate()

    assert host._estimate_loaded is False
    assert host.delete_estimate_button.isEnabled() is False
    assert host.focus_calls == [0]
    assert host.status_calls[-1] == ("Estimate MISS1 not found. Starting new entry.", 4000)


def test_load_estimate_reports_error_status(workflow_host):
    host, controller = workflow_host
    host.voucher_edit.setText("ERR1")
    host.presenter = types.SimpleNamespace(
        load_estimate=lambda voucher_no: (_ for _ in ()).throw(RuntimeError("load boom"))
    )

    controller.load_estimate()

    assert host.status_calls[-1] == ("Error loading estimate: load boom", 4000)


def test_safe_load_estimate_respects_unsaved_cancel(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.voucher_edit.setText("V202")
    host._unsaved_changes = True
    _MessageBoxStub.question_return = _MessageBoxStub.No
    calls = []
    monkeypatch.setattr(
        workflow_module.EstimateEntryWorkflowController,
        "load_estimate",
        lambda self: calls.append("load"),
    )

    controller.safe_load_estimate()

    assert calls == []
    assert controller._loading_estimate is False


def test_safe_load_estimate_ignores_empty_voucher(workflow_host, monkeypatch):
    _host, controller = workflow_host
    calls = []
    monkeypatch.setattr(
        workflow_module.EstimateEntryWorkflowController,
        "load_estimate",
        lambda self: calls.append("load"),
    )

    controller.safe_load_estimate()

    assert calls == []


def test_save_estimate_success_invokes_print_and_clear(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.voucher_edit.setText("S001")
    host.note_edit.setText("note")
    host.print_calls = 0
    host.clear_calls = []
    host.print_estimate = lambda: setattr(host, "print_calls", host.print_calls + 1)
    host.clear_form = lambda confirm=False: host.clear_calls.append(confirm)
    host._update_view_model_snapshot = lambda: host.status_calls.append(("snapshot", 0))
    host.presenter = object()

    class _ServiceStub:
        def __init__(self, view_model):
            self.view_model = view_model

        def execute_save(self, **kwargs):
            del kwargs
            return SaveOutcome(success=True, message="Saved ok"), object()

    monkeypatch.setattr(workflow_module, "EstimateEntryPersistenceService", _ServiceStub)

    controller.save_estimate()

    assert ("Saving estimate S001...", 2000) in host.status_calls
    assert ("Saved ok", 5000) in host.status_calls
    assert host.print_calls == 1
    assert host.clear_calls == [False]
    assert any(args[1] == "Success" for args in _MessageBoxStub.information_calls)


def test_save_estimate_requires_voucher_number(workflow_host):
    _host, controller = workflow_host

    controller.save_estimate()

    assert any(args[1] == "Input Error" for args in _MessageBoxStub.warning_calls)


def test_save_estimate_returns_when_presenter_missing(workflow_host):
    host, controller = workflow_host
    host.voucher_edit.setText("S003")

    controller.save_estimate()

    assert ("Saving estimate S003...", 2000) not in host.status_calls


def test_save_estimate_handles_exception(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.voucher_edit.setText("S004")
    host._update_view_model_snapshot = lambda: None
    host.presenter = object()

    class _ServiceStub:
        def __init__(self, view_model):
            self.view_model = view_model

        def execute_save(self, **kwargs):
            del kwargs
            raise RuntimeError("save blew up")

    monkeypatch.setattr(workflow_module, "EstimateEntryPersistenceService", _ServiceStub)

    controller.save_estimate()

    assert any(args[1] == "Save Error" and args[2] == "save blew up" for args in _MessageBoxStub.critical_calls)


def test_save_estimate_failure_shows_critical(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.voucher_edit.setText("S002")
    host._update_view_model_snapshot = lambda: None
    host.presenter = object()

    class _ServiceStub:
        def __init__(self, view_model):
            self.view_model = view_model

        def execute_save(self, **kwargs):
            del kwargs
            return SaveOutcome(success=False, message="No good"), object()

    monkeypatch.setattr(workflow_module, "EstimateEntryPersistenceService", _ServiceStub)

    controller.save_estimate()

    assert ("No good", 5000) in host.status_calls
    assert any(args[1] == "Save Error" for args in _MessageBoxStub.critical_calls)


def test_delete_current_estimate_success_clears_form(workflow_host):
    host, controller = workflow_host
    host.voucher_edit.setText("DEL1")
    host.presenter = types.SimpleNamespace(delete_estimate=lambda voucher_no: True)
    host.clear_calls = []
    host.clear_form = lambda confirm=False: host.clear_calls.append(confirm)

    controller.delete_current_estimate()

    assert host.clear_calls == [False]
    assert host.status_calls[-1] == ("Estimate DEL1 deleted.", 3000)


def test_delete_current_estimate_failure_shows_warning(workflow_host):
    host, controller = workflow_host
    host.voucher_edit.setText("DEL2")
    host.presenter = types.SimpleNamespace(delete_estimate=lambda voucher_no: False)

    controller.delete_current_estimate()

    assert any(args[1] == "Error" for args in _MessageBoxStub.warning_calls)


def test_print_estimate_handles_preview_validation_error(workflow_host):
    host, controller = workflow_host
    host.voucher_edit.setText("P001")
    host._build_current_estimate_preview_data = lambda _voucher: (_ for _ in ()).throw(
        ValueError("No valid items found to save.")
    )

    controller.print_estimate()

    assert any(
        "Add at least one valid item before opening print preview." in args[2]
        for args in _MessageBoxStub.warning_calls
    )


def test_print_estimate_handles_preview_build_exception(workflow_host):
    host, controller = workflow_host
    host.voucher_edit.setText("P002")
    host._build_current_estimate_preview_data = lambda _voucher: (_ for _ in ()).throw(
        RuntimeError("bad preview")
    )

    controller.print_estimate()

    assert any(args[1] == "Print Error" for args in _MessageBoxStub.critical_calls)


def test_print_preview_ready_closes_progress_and_shows_preview(workflow_host):
    _host, controller = workflow_host
    progress = _ProgressStub()
    shown = []
    print_manager = types.SimpleNamespace(
        show_preview=lambda payload, parent_widget=None: shown.append((payload, parent_widget))
    )
    controller._print_preview_request_id = 5

    controller._on_estimate_print_preview_ready(
        5,
        {"html": "<p>ok</p>"},
        print_manager=print_manager,
        progress=progress,
    )

    assert progress.closed == 1
    assert shown and shown[0][0] == {"html": "<p>ok</p>"}


def test_print_preview_ready_ignores_stale_request(workflow_host):
    _host, controller = workflow_host
    progress = _ProgressStub()
    shown = []
    controller._print_preview_request_id = 8
    print_manager = types.SimpleNamespace(
        show_preview=lambda payload, parent_widget=None: shown.append((payload, parent_widget))
    )

    controller._on_estimate_print_preview_ready(
        7,
        {"html": "<p>stale</p>"},
        print_manager=print_manager,
        progress=progress,
    )

    assert progress.closed == 0
    assert shown == []


def test_print_preview_ready_none_payload_routes_to_error(workflow_host, monkeypatch):
    _host, controller = workflow_host
    progress = _ProgressStub()
    calls = []
    controller._print_preview_request_id = 9
    monkeypatch.setattr(
        workflow_module.EstimateEntryWorkflowController,
        "_on_estimate_print_preview_error",
        lambda self, request_id, message, *, progress: calls.append((request_id, message, progress)),
    )

    controller._on_estimate_print_preview_ready(
        9,
        None,
        print_manager=object(),
        progress=progress,
    )

    assert calls and calls[0][1] == "Estimate preview data could not be prepared."


def test_print_preview_error_shows_message(workflow_host):
    _host, controller = workflow_host
    progress = _ProgressStub()
    controller._print_preview_request_id = 3

    controller._on_estimate_print_preview_error(3, "bad payload", progress=progress)

    assert progress.closed == 1
    assert any("bad payload" in args[2] for args in _MessageBoxStub.critical_calls)


def test_print_preview_error_ignores_stale_request(workflow_host):
    _host, controller = workflow_host
    progress = _ProgressStub()
    controller._print_preview_request_id = 5

    controller._on_estimate_print_preview_error(4, "stale", progress=progress)

    assert progress.closed == 0
    assert _MessageBoxStub.critical_calls == []


def test_finalize_print_preview_build_disposes_resources(workflow_host):
    host, controller = workflow_host
    progress = _ProgressStub()
    thread = _ThreadStub()
    worker = _WorkerDisposeStub()
    controller._active_print_preview_workers = {thread: worker}

    controller._finalize_estimate_print_preview_build(
        1,
        thread=thread,
        worker=worker,
        progress=progress,
    )

    assert progress.closed == 1
    assert progress.deleted == 1
    assert thread.quit_calls == 1
    assert thread.wait_calls == [2000]
    assert worker.deleted == 1
    assert thread.deleted == 1
    assert controller._active_print_preview_workers == {}


def test_clear_form_resets_modes_and_focuses_first_row(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.voucher_edit.setText("OLD")
    host.note_edit.setText("old note")
    host.silver_rate_spin.setValue(91.0)
    host.last_balance_silver = 5.0
    host.last_balance_amount = 100.0
    host.return_mode = True
    host.silver_bar_mode = True
    host.presenter = types.SimpleNamespace(generate_voucher=lambda: host.status_calls.append(("generated", 0)))
    monkeypatch.setattr(workflow_module.QTimer, "singleShot", lambda _ms, fn: fn())
    host.toggle_return_mode = lambda: setattr(host, "return_mode", False)
    host.toggle_silver_bar_mode = lambda: setattr(host, "silver_bar_mode", False)

    controller.clear_form(confirm=False)

    assert host.voucher_edit.text() == ""
    assert host.note_edit.text() == ""
    assert host.silver_rate_spin.value() == pytest.approx(0.0)
    assert host.last_balance_silver == 0.0
    assert host.last_balance_amount == 0.0
    assert host.clear_rows_calls == 1
    assert host.add_row_calls == 1
    assert host.calculate_totals_calls == 1
    assert host.focus_calls[-1] == 0
    assert host._unsaved_changes is False


def test_confirm_exit_respects_unsaved_state(workflow_host):
    host, controller = workflow_host
    assert controller.confirm_exit() is True

    host._unsaved_changes = True
    _MessageBoxStub.question_return = _MessageBoxStub.No
    assert controller.confirm_exit() is False
    _MessageBoxStub.question_return = _MessageBoxStub.Yes
    assert controller.confirm_exit() is True


def test_show_history_calls_presenter(workflow_host):
    host, controller = workflow_host
    calls = []
    host.presenter = types.SimpleNamespace(open_history=lambda: calls.append("history"))

    controller.show_history()

    assert calls == ["history"]


def test_toggle_modes_updates_view_model_and_indicator(workflow_host):
    host, controller = workflow_host

    controller.toggle_return_mode()
    assert host.return_mode is True
    assert host.view_model.return_mode is True
    assert host.mode_indicator_label.text() == "Mode: Return Items"

    controller.toggle_silver_bar_mode()
    assert host.return_mode is False
    assert host.view_model.silver_bar_mode is True
    assert host.mode_indicator_label.text() == "Mode: Silver Bars"
    assert host._adapter.refreshed == 2
    assert host._adapter.focus_calls == [True, True]


def test_delete_current_row_updates_totals_and_focus(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.item_table._current_row = 1
    host.item_table._row_count = 3
    monkeypatch.setattr(workflow_module.QTimer, "singleShot", lambda _ms, fn: fn())
    host._totals_incremental_is_active = lambda: False

    controller.delete_current_row()

    assert host.item_table.deleted_rows == [1]
    assert host.calculate_totals_calls == 1
    assert host.mark_unsaved_calls == 1
    assert host.item_table.current_cells[-1] == (1, workflow_module.COL_CODE)


def test_delete_current_row_rejects_only_row(workflow_host):
    host, controller = workflow_host
    host.item_table._current_row = 0
    host.item_table._row_count = 1

    controller.delete_current_row()

    assert any("Cannot delete the only row." in args[2] for args in _MessageBoxStub.warning_calls)


def test_prompt_item_selection_and_open_history_dialog(workflow_host, monkeypatch):
    host, controller = workflow_host

    class _SelectionDialog:
        def __init__(self, db_manager, code, parent=None):
            self.db_manager = db_manager
            self.code = code
            self.parent = parent

        def exec_(self):
            return workflow_module.QDialog.Accepted

        def get_selected_item(self):
            return {"code": "SEL001"}

    class _HistoryDialog:
        def __init__(self, db_manager, main_window_ref=None, parent=None):
            self.db_manager = db_manager
            self.main_window_ref = main_window_ref
            self.parent = parent
            self.selected_voucher = "H001"

        def exec_(self):
            return workflow_module.QDialog.Accepted

    monkeypatch.setattr(workflow_module, "ItemSelectionDialog", _SelectionDialog)
    monkeypatch.setitem(
        __import__("sys").modules,
        "silverestimate.ui.estimate_history",
        types.SimpleNamespace(EstimateHistoryDialog=_HistoryDialog),
    )

    selected = controller.prompt_item_selection("bad")
    voucher = controller.open_history_dialog()

    assert selected == {"code": "SEL001"}
    assert voucher == "H001"


def test_show_silver_bar_management_and_alias(workflow_host):
    host, controller = workflow_host
    calls = []
    host.main_window = types.SimpleNamespace(show_silver_bars=lambda: calls.append("bars"))

    controller.show_silver_bar_management()
    controller.show_silver_bars()

    assert calls == ["bars", "bars"]


def test_apply_loaded_estimate_populates_rows_and_normalizes_values(workflow_host):
    host, controller = workflow_host
    loaded = LoadedEstimate(
        voucher_no="L001",
        date="2026-03-19",
        silver_rate=82.5,
        note="loaded note",
        last_balance_silver=1.5,
        last_balance_amount=120.0,
        items=(
            SaveItem(
                code="pc01",
                row_number=1,
                name="PC Item",
                gross=5.0,
                poly=0.0,
                net_wt=5.0,
                purity=92.5,
                wage_rate=10.0,
                pieces=0,
                wage=50.0,
                fine=4.625,
                is_return=False,
                is_silver_bar=False,
                wage_type="PC",
            ),
            SaveItem(
                code="wt01",
                row_number=2,
                name="WT Item",
                gross=3.0,
                poly=0.0,
                net_wt=3.0,
                purity=80.0,
                wage_rate=5.0,
                pieces=9,
                wage=15.0,
                fine=2.4,
                is_return=True,
                is_silver_bar=False,
                wage_type="WT",
            ),
        ),
    )

    assert controller.apply_loaded_estimate(loaded) is True
    assert host.date_edit.date().toString("yyyy-MM-dd") == "2026-03-19"
    assert host.silver_rate_spin.value() == pytest.approx(82.5)
    assert host.note_edit.text() == "loaded note"
    assert host.delete_estimate_button.isEnabled() is True
    assert host.voucher_edit.text() == "L001"
    assert host.add_row_calls == 1
    assert host.calculate_totals_calls == 1
    assert host.schedule_columns_calls == [True]
    assert len(host.item_table.replaced_rows) == 2
    assert host.item_table.replaced_rows[0].code == "PC01"
    assert host.item_table.replaced_rows[0].pieces == 1
    assert host.item_table.replaced_rows[1].code == "WT01"
    assert host.item_table.replaced_rows[1].pieces == 0


def test_apply_loaded_estimate_returns_false_on_error(workflow_host):
    host, controller = workflow_host
    host.item_table.replace_all_rows = lambda rows: (_ for _ in ()).throw(RuntimeError("replace failed"))
    loaded = LoadedEstimate(
        voucher_no="FAILLOAD",
        date="bad-date",
        silver_rate=0.0,
        note="",
        last_balance_silver=0.0,
        last_balance_amount=0.0,
        items=(),
    )

    assert controller.apply_loaded_estimate(loaded) is False


def test_apply_refreshed_live_rate_updates_label_and_status(workflow_host):
    host, controller = workflow_host

    controller._apply_refreshed_live_rate(92500)
    assert host.refresh_rate_button.isEnabled() is True
    assert host.live_rate_value_label.text() == "₹ 92.50 /g"
    assert host.status_calls[-1] == ("Live rate refreshed.", 2000)

    controller._apply_refreshed_live_rate("not-a-number")
    assert host.live_rate_value_label.text() == "N/A"
    assert host.status_calls[-1] == ("Live rate unavailable.", 3000)


def test_handle_silver_rate_changed_schedules_totals_and_unsaved(workflow_host):
    host, controller = workflow_host

    controller._handle_silver_rate_changed()

    assert host.schedule_totals_calls == 1
    assert host.mark_unsaved_calls == 1


def test_update_view_model_snapshot_copies_widget_state(workflow_host):
    host, controller = workflow_host
    host.item_table.get_all_rows = lambda: (
        EstimateEntryRowState(code="A1", row_index=1),
        EstimateEntryRowState(code="B2", row_index=2),
    )
    host.voucher_edit.setText("VM001")
    host.note_edit.setText("note me")
    host.silver_rate_spin.setValue(95.5)
    host.last_balance_silver = 1.25
    host.last_balance_amount = 70.0
    host.return_mode = True

    controller._update_view_model_snapshot()

    assert [row.code for row in host.view_model.rows()] == ["A1", "B2"]
    assert host.view_model.get_voucher_metadata()["voucher_number"] == "VM001"
    assert host.view_model.silver_rate == pytest.approx(95.5)
    assert host.view_model.last_balance_silver == pytest.approx(1.25)
    assert host.view_model.return_mode is True


def test_build_current_estimate_preview_data_reports_skipped_rows(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.view_model.set_voucher_metadata(
        voucher_number="PX01",
        voucher_date="2026-03-20",
        voucher_note="preview note",
    )
    host._update_view_model_snapshot = lambda: None

    class _Preparation:
        skipped_rows = [2, 4]
        payload = types.SimpleNamespace(
            silver_rate=90.0,
            note="preview note",
            last_balance_silver=1.0,
            last_balance_amount=50.0,
            items=[
                types.SimpleNamespace(
                    row_number=1,
                    code="REG001",
                    name="Regular",
                    gross=10.0,
                    poly=1.0,
                    net_wt=9.0,
                    purity=92.5,
                    wage_rate=10.0,
                    pieces=0,
                    wage=90.0,
                    fine=8.325,
                    is_return=False,
                    is_silver_bar=False,
                )
            ],
        )

    class _ServiceStub:
        def __init__(self, view_model):
            self.view_model = view_model

        def prepare_save_payload(self, **kwargs):
            del kwargs
            return _Preparation()

    monkeypatch.setattr(workflow_module, "EstimateEntryPersistenceService", _ServiceStub)

    preview = controller._build_current_estimate_preview_data("PX01")

    assert host.status_calls[-1] == ("Preview skipped invalid rows: 2, 4", 5000)
    assert preview["header"]["voucher_no"] == "PX01"
    assert preview["header"]["note"] == "preview note"
    assert preview["items"][0]["item_code"] == "REG001"
    assert preview["items"][0]["is_return"] == 0


def test_get_cell_helpers_and_last_balance_dialog(workflow_host, monkeypatch):
    host, controller = workflow_host
    host.item_table.text_cells[(0, workflow_module.COL_CODE)] = "AB01"
    host.item_table.text_cells[(0, 99)] = "x"
    monkeypatch.setattr(QDialog, "exec_", lambda self: True)

    controller.show_last_balance_dialog()

    assert controller._get_row_code(0) == "AB01"
    assert controller._get_cell_str(0, 99) == "x"
    assert host.calculate_totals_calls == 1
    assert host.mark_unsaved_calls == 1


def test_refresh_silver_rate_emits_none_on_failure(workflow_host, monkeypatch):
    host, controller = workflow_host

    class _ThreadStubImmediate:
        def __init__(self, *, target=None, daemon=None):
            self._target = target
            self.daemon = daemon

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(workflow_module.threading, "Thread", _ThreadStubImmediate)

    def _boom(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("offline")

    fake_module = types.SimpleNamespace(
        fetch_broadcast_rate_exact=_boom,
        fetch_silver_agra_local_mohar_rate=lambda timeout=7: (None, None),
    )
    monkeypatch.setitem(__import__("sys").modules, "silverestimate.services.dda_rate_fetcher", fake_module)

    controller.refresh_silver_rate()

    assert host.refresh_rate_button.isEnabled() is False
    assert host.status_calls[0] == ("Refreshing live silver rate...", 2000)
    assert host.live_rate_fetched.emitted == [None]
