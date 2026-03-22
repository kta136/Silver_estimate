import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pytest

from silverestimate.infrastructure.app_constants import APP_TITLE
from silverestimate.ui.estimate_entry_logic.constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_NET_WT,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from silverestimate.ui.main_window import MainWindow


@dataclass
class FakeDbManager:
    """In-memory stand-in for the real database manager."""

    items: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "RING001": {
                "code": "RING001",
                "name": "Sample Ring",
                "purity": 92.5,
                "wage_rate": 12.0,
                "wage_type": "WT",
            }
        }
    )
    generate_calls: int = 0
    saved_estimates: List[Dict[str, Any]] = field(default_factory=list)
    preload_started: bool = False
    closed: bool = False
    flush_on_queued: Optional[Any] = None
    flush_on_done: Optional[Any] = None

    def __post_init__(self) -> None:
        self.item_cache_controller = None

    # --- Lifecycle -------------------------------------------------
    def start_preload_item_cache(self) -> None:
        self.preload_started = True

    def set_flush_status_callbacks(self, *, on_queued=None, on_done=None) -> None:
        self.flush_on_queued = on_queued
        self.flush_on_done = on_done

    def emit_flush_queued(self) -> None:
        if self.flush_on_queued:
            self.flush_on_queued()

    def emit_flush_done(self) -> None:
        if self.flush_on_done:
            self.flush_on_done()

    def close(self) -> None:
        self.closed = True

    # --- Estimate workflow ----------------------------------------
    def generate_voucher_no(self) -> str:
        self.generate_calls += 1
        return f"TST{self.generate_calls:03d}"

    def get_item_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        return self.items.get(code.strip().upper())

    def get_estimate_by_voucher(self, voucher_no: str) -> Optional[Dict[str, Any]]:
        return None

    def save_estimate_with_returns(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items,
        return_items,
        totals,
    ) -> bool:
        self.saved_estimates.append(
            {
                "voucher_no": voucher_no,
                "date": date,
                "silver_rate": silver_rate,
                "regular": list(regular_items or []),
                "returns": list(return_items or []),
                "totals": dict(totals or {}),
            }
        )
        return True

    def delete_single_estimate(self, voucher_no: str) -> bool:
        return True

    def delete_all_estimates(self) -> bool:
        return True

    def drop_tables(self) -> bool:
        return True

    def setup_database(self) -> bool:
        return True

    @property
    def last_error(self) -> Optional[str]:
        return None


class StubLiveRateController:
    """Lightweight replacement for the live rate controller used in tests."""

    instances: List["StubLiveRateController"] = []

    def __init__(self, *, parent, widget_getter, status_callback, logger=None, **_):
        self.parent = parent
        self.widget_getter = widget_getter
        self.status_callback = status_callback
        self.logger = logger
        self.initialize_called = False
        self.shutdown_called = False
        self.refresh_calls = 0
        self.visibility_calls = 0
        self.timer_calls = 0
        StubLiveRateController.instances.append(self)

    def initialize(self) -> None:
        self.initialize_called = True

    def shutdown(self) -> None:
        self.shutdown_called = True

    def refresh_now(self) -> None:
        self.refresh_calls += 1

    def apply_visibility_settings(self) -> bool:
        self.visibility_calls += 1
        return True

    def apply_timer_settings(self, **_) -> None:
        self.timer_calls += 1


@pytest.fixture
def main_window_fixture(qt_app, settings_stub, monkeypatch):
    """Create a MainWindow instance with test doubles injected."""
    previous_quit_on_close = qt_app.quitOnLastWindowClosed()
    qt_app.setQuitOnLastWindowClosed(False)
    StubLiveRateController.instances.clear()
    monkeypatch.setattr("PyQt5.QtWidgets.QApplication.quit", lambda self=None: None)
    monkeypatch.setattr(
        "silverestimate.controllers.live_rate_controller.LiveRateController",
        StubLiveRateController,
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.windows_integration.apply_taskbar_icon",
        lambda *args, **kwargs: 12345,
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.windows_integration.destroy_icon_handle",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry.EstimateEntryWidget.confirm_exit",
        lambda self: True,
    )
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry.EstimateEntryWidget._safe_edit_item",
        lambda self, *_: None,
    )

    db = FakeDbManager()
    logger = logging.getLogger("test.mainwindow")
    window = MainWindow(db_manager=db, logger=logger)
    live_rate = StubLiveRateController.instances[-1]

    try:
        yield {"window": window, "db": db, "live_rate": live_rate}
    finally:
        if window:
            window.close()
            window.deleteLater()
            qt_app.processEvents()
        qt_app.setQuitOnLastWindowClosed(previous_quit_on_close)
        StubLiveRateController.instances.clear()


def test_main_window_startup_sets_up_estimate_view(main_window_fixture, qt_app, qtbot):
    context = main_window_fixture
    window = context["window"]
    db = context["db"]
    live_rate = context["live_rate"]

    # Main view should be present and active.
    assert window.stack.currentWidget() is window.estimate_widget
    assert window.stack.count() == 1
    assert window.windowTitle() == f"{APP_TITLE}[*]"

    # Startup side effects.
    assert db.generate_calls == 1  # Voucher generated for initial form.
    assert db.preload_started is False
    assert live_rate.initialize_called is True

    # Main navigation wired (menu action created by controller).
    assert hasattr(window, "_menu_estimate_action")
    assert window._menu_estimate_action is not None
    assert not window._menu_estimate_action.icon().isNull()
    assert not window._menu_item_master_action.icon().isNull()
    assert not window._menu_silver_action.icon().isNull()
    assert not window.refresh_rate_action.icon().isNull()

    widget = window.estimate_widget
    assert not widget.save_button.icon().isNull()
    assert not widget.print_button.icon().isNull()
    assert not widget.clear_button.icon().isNull()
    assert not widget.delete_row_button.icon().isNull()
    assert not widget.return_toggle_button.icon().isNull()
    assert not widget.silver_bar_toggle_button.icon().isNull()
    assert not widget.history_button.icon().isNull()
    assert not widget.last_balance_button.icon().isNull()
    assert not widget.silver_bars_button.icon().isNull()
    assert not widget.delete_estimate_button.icon().isNull()

    assert widget.save_button.text() == ""
    assert widget.print_button.text() == ""
    assert widget.clear_button.text() == ""
    assert widget.delete_row_button.text() == ""
    assert widget.return_toggle_button.text() == ""
    assert widget.silver_bar_toggle_button.text() == ""
    assert widget.history_button.text() == ""
    assert widget.last_balance_button.text() == ""
    assert widget.silver_bars_button.text() == ""
    assert widget.delete_estimate_button.text() == ""

    assert widget.save_button.accessibleName() == "Save"
    assert widget.print_button.accessibleName() == "Print"
    assert widget.clear_button.accessibleName() == "New"
    assert widget.delete_row_button.accessibleName() == "Delete Row"
    assert widget.return_toggle_button.accessibleName() == "Return"
    assert widget.silver_bar_toggle_button.accessibleName() == "Bar Mode"
    assert widget.last_balance_button.accessibleName() == "Balance"
    assert widget.history_button.accessibleName() == "History"
    assert widget.silver_bars_button.accessibleName() == "Bar List"
    assert widget.delete_estimate_button.accessibleName() == "Delete Estimate"

    # Public helpers delegate to controller.
    live_rate.refresh_calls = 0
    window.refresh_live_rate_now()
    assert live_rate.refresh_calls == 1

    window.reconfigure_rate_visibility_from_settings()
    assert live_rate.visibility_calls == 1

    window.reconfigure_rate_timer_from_settings()
    assert live_rate.timer_calls == 1

    status_calls = []
    original_show_inline_status = widget.show_inline_status

    def _capture_status(message, timeout=3000, level="info"):
        status_calls.append((message, timeout, level))
        return original_show_inline_status(message, timeout=timeout, level=level)

    widget.show_inline_status = _capture_status
    db.emit_flush_queued()
    qtbot.waitUntil(lambda: status_calls != [], timeout=1000)
    assert status_calls[-1] == ("Saving.", 1000, "info")
    db.emit_flush_done()
    qtbot.waitUntil(lambda: status_calls[-1] == ("", 0, "info"), timeout=1000)

    # Closing should invoke live-rate shutdown and database close.
    window.close()
    qtbot.waitUntil(lambda: live_rate.shutdown_called is True, timeout=1000)
    qtbot.waitUntil(lambda: db.closed is True, timeout=1000)


def test_user_entry_updates_totals_and_view_model(main_window_fixture, qtbot):
    context = main_window_fixture
    window = context["window"]
    db = context["db"]

    widget = window.estimate_widget
    table = widget.item_table

    qtbot.waitUntil(lambda: table.rowCount() > 0, timeout=1500)

    # Simulate entering an item code the way the presenter expects.
    assert widget.presenter.handle_item_code(0, "RING001") is True
    qtbot.waitUntil(
        lambda: table.get_cell_text(0, COL_CODE).strip().upper() == "RING001",
        timeout=1500,
    )

    # Populate user-editable values.
    widget.current_row = 0
    table.set_cell_text(0, COL_GROSS, "10")
    table.set_cell_text(0, COL_POLY, "0.5")
    table.set_cell_text(0, COL_PURITY, "92.5")
    table.set_cell_text(0, COL_WAGE_RATE, "12")

    # Trigger chained calculations (net, fine, wage, totals).
    widget.calculate_net_weight()
    widget.calculate_totals()
    qtbot.waitUntil(
        lambda: table.get_cell_text(0, COL_WAGE_AMT).strip() not in {"", "0", "0.0"},
        timeout=1500,
    )

    # Row cells reflect calculated values.
    assert float(table.get_cell_text(0, COL_NET_WT)) == pytest.approx(9.5, rel=1e-3)
    assert float(table.get_cell_text(0, COL_FINE_WT)) == pytest.approx(8.79, rel=1e-3)
    assert float(table.get_cell_text(0, COL_WAGE_AMT)) == pytest.approx(114.0)

    # Totals panel displays computed aggregates.
    assert float(widget.overall_gross_label.text()) == pytest.approx(10.0)
    assert float(widget.overall_poly_label.text()) == pytest.approx(0.5)
    assert float(widget.total_net_label.text()) == pytest.approx(9.5)
    assert float(widget.total_fine_label.text()) == pytest.approx(8.79, rel=1e-3)
    assert float(widget.net_fine_label.text()) == pytest.approx(8.79, rel=1e-3)

    # View-model captures the active row for downstream workflows.
    widget._update_view_model_snapshot()
    active_rows = widget.view_model.active_rows()
    assert len(active_rows) == 1
    row_state = active_rows[0]
    assert row_state.code == "RING001"
    assert row_state.gross == pytest.approx(10.0)
    assert row_state.poly == pytest.approx(0.5)
    assert row_state.net_weight == pytest.approx(9.5)
    assert row_state.fine_weight == pytest.approx(8.7875, rel=1e-3)

    # No extra voucher generation during interactions.
    assert db.generate_calls == 1
