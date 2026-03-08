import types

import pytest
from PyQt5.QtCore import QDate, QEventLoop, Qt, QTimer
from PyQt5.QtWidgets import QDialog, QHeaderView, QLineEdit, QMessageBox, QWidget

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.presenter.estimate_entry_presenter import LoadedEstimate, SaveItem
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_components.totals_panel import TotalsPanel
from silverestimate.ui.estimate_entry_logic import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from tests.factories import regular_item, return_item, silver_bar_item


@pytest.fixture()
def fake_db(tmp_path):
    class _DB:
        def __init__(self):
            self.item_cache_controller = None
            self.generate_calls = 0

        def generate_voucher_no(self):
            self.generate_calls += 1
            return "TEST123"

        def drop_tables(self):
            return True

        def setup_database(self):
            return True

        def delete_all_estimates(self):
            return True

        def get_item_by_code(self, code):
            return {"wage_type": "WT", "wage_rate": 10}

    return _DB()


def _set_row(widget, row, item):
    table = widget.item_table
    while table.rowCount() <= row:
        widget.add_empty_row()
    table.set_cell_text(row, COL_CODE, str(item["code"]))
    if item.get("name"):
        table.set_cell_text(row, COL_ITEM_NAME, str(item["name"]))
    table.set_cell_text(row, COL_GROSS, str(item["gross"]))
    table.set_cell_text(row, COL_POLY, str(item["poly"]))
    table.set_cell_text(row, COL_PURITY, str(item["purity"]))
    table.set_cell_text(row, COL_WAGE_RATE, str(item["wage_rate"]))
    table.set_cell_text(row, COL_PIECES, str(item["pieces"]))
    widget.current_row = row
    net = max(0.0, float(item["gross"]) - float(item["poly"]))
    fine = net * (float(item["purity"]) / 100.0)
    wage = net * float(item["wage_rate"])

    table.set_cell_text(row, COL_NET_WT, f"{net:.2f}")
    table.set_cell_text(row, COL_FINE_WT, f"{fine:.2f}")
    table.set_cell_text(row, COL_WAGE_AMT, f"{wage:.0f}")

    # Manually set type for test
    if item.get("is_silver_bar"):
        table.set_row_category(row, EstimateLineCategory.SILVER_BAR)
    elif item.get("is_return"):
        table.set_row_category(row, EstimateLineCategory.RETURN)
    else:
        table.set_row_category(row, EstimateLineCategory.REGULAR)

    widget.calculate_totals()

    return table


class _RepositoryStub:
    def __init__(self, db):
        self.db = db

    def generate_voucher_no(self):
        return self.db.generate_voucher_no()

    def load_estimate(self, voucher_no):
        loader = getattr(self.db, "get_estimate_by_voucher", None)
        if callable(loader):
            return loader(voucher_no)
        return None

    def fetch_item(self, code):
        return self.db.get_item_by_code(code)

    def save_estimate(
        self, voucher_no, date, silver_rate, regular_items, return_items, totals
    ):
        saver = getattr(self.db, "save_estimate_with_returns", None)
        if callable(saver):
            return bool(
                saver(
                    voucher_no,
                    date,
                    silver_rate,
                    list(regular_items or []),
                    list(return_items or []),
                    dict(totals or {}),
                )
            )
        return True

    def sync_silver_bars_for_estimate(self, voucher_no, bars):
        syncer = getattr(self.db, "sync_silver_bars_for_estimate", None)
        if callable(syncer):
            added, failed = syncer(voucher_no, list(bars or []))
            return int(added or 0), int(failed or 0)
        return 0, len(list(bars or []))

    def last_error(self):
        return getattr(self.db, "last_error", None)

    def delete_estimate(self, voucher_no):
        deleter = getattr(self.db, "delete_single_estimate", None)
        if callable(deleter):
            return bool(deleter(voucher_no))
        return True


def _make_widget(db_manager):
    main_window_stub = types.SimpleNamespace(
        show_inline_status=lambda *a, **k: None,
        show_silver_bars=lambda: None,
    )
    repository = _RepositoryStub(db_manager)
    widget = EstimateEntryWidget(db_manager, main_window_stub, repository)
    widget.presenter.handle_item_code = lambda row, code: False
    try:
        widget.item_table.cellChanged.disconnect(widget.handle_cell_changed)
    except TypeError:
        pass
    return widget


def _pump_events(wait_ms: int = 20) -> None:
    loop = QEventLoop()
    QTimer.singleShot(wait_ms, loop.quit)
    loop.exec_()


def _find_named_widget(root: QWidget, object_name: str) -> QWidget | None:
    for child in root.findChildren(QWidget):
        if child.objectName() == object_name:
            return child
    return None


def test_widget_generates_voucher_on_init(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        assert fake_db.generate_calls == 1
        assert widget.voucher_edit.text() == "TEST123"
    finally:
        widget.deleteLater()


def test_widget_calculates_totals(qt_app, fake_db):
    widget = _make_widget(fake_db)
    table = _set_row(
        widget,
        0,
        regular_item(gross=10, poly=1, purity=92.5, wage_rate=10),
    )

    assert float(table.get_cell_text(0, COL_NET_WT)) == pytest.approx(9.00)
    expected_fine = (10 - 1) * (92.5 / 100.0)
    # Using larger tolerance due to rounding issues (8.325 -> 8.33)
    assert float(table.get_cell_text(0, COL_FINE_WT)) == pytest.approx(
        expected_fine, abs=0.01
    )
    assert float(table.get_cell_text(0, COL_WAGE_AMT)) == pytest.approx(90.0)

    assert float(widget.total_gross_label.text()) == pytest.approx(10.0)
    assert float(widget.total_net_label.text()) == pytest.approx(9.0)
    assert float(widget.total_fine_label.text()) == pytest.approx(8.325, abs=0.01)

    widget.deleteLater()


def test_widget_multi_row_totals(qt_app, fake_db):
    widget = _make_widget(fake_db)

    _set_row(widget, 0, regular_item(gross=10, poly=1, purity=92.5, wage_rate=10))

    widget.toggle_return_mode()
    _set_row(widget, 1, return_item(gross=2.5, poly=0.5, purity=80, wage_rate=0))
    widget.toggle_return_mode()

    widget.toggle_silver_bar_mode()
    _set_row(widget, 2, silver_bar_item(gross=3.0, poly=0.0, purity=99.9, wage_rate=0))
    widget.toggle_silver_bar_mode()

    table = widget.item_table
    widget.calculate_totals()

    assert table.get_cell_text(0, COL_TYPE) == "Regular"
    assert table.get_cell_text(1, COL_TYPE) == "Return"
    assert table.get_cell_text(2, COL_TYPE) == "Silver Bar"

    assert float(widget.total_gross_label.text()) == pytest.approx(10.0)
    assert float(widget.return_gross_label.text()) == pytest.approx(2.5)
    assert float(widget.bar_gross_label.text()) == pytest.approx(3.0)

    widget.deleteLater()


def test_incremental_totals_match_full_single_row_edit(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = _set_row(
            widget,
            0,
            regular_item(gross=10, poly=1, purity=92.5, wage_rate=10),
        )
        assert widget._totals_incremental_is_active()

        table.set_cell_text(0, COL_GROSS, "12.0")
        widget.handle_cell_changed(0, COL_GROSS)
        _pump_events(150)

        assert float(widget.total_gross_label.text()) == pytest.approx(12.0)
        assert float(widget.total_net_label.text()) == pytest.approx(11.0)
        assert float(widget.total_fine_label.text()) == pytest.approx(10.175, abs=0.01)
        assert float(widget.net_wage_label.text()) == pytest.approx(110.0)
    finally:
        widget.deleteLater()


def test_incremental_row_edit_applies_totals_without_recalc_schedule(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = _set_row(
            widget,
            0,
            regular_item(gross=10, poly=1, purity=92.5, wage_rate=10),
        )
        assert widget._totals_incremental_is_active()

        scheduled = {"count": 0}

        def _unexpected_schedule(*args, **kwargs):
            scheduled["count"] += 1
            raise AssertionError("incremental row edit should not schedule totals")

        widget._schedule_totals_recalc = _unexpected_schedule

        table.set_cell_text(0, COL_GROSS, "12.0")
        widget.handle_cell_changed(0, COL_GROSS)

        assert scheduled["count"] == 0
        assert float(widget.total_gross_label.text()) == pytest.approx(12.0)
        assert float(widget.total_net_label.text()) == pytest.approx(11.0)
        assert float(widget.total_fine_label.text()) == pytest.approx(10.175, abs=0.01)
        assert float(widget.net_wage_label.text()) == pytest.approx(110.0)
    finally:
        widget.deleteLater()


def test_incremental_totals_match_full_multi_row_mixed_categories(
    qt_app, qtbot, fake_db
):
    widget = _make_widget(fake_db)
    try:
        _set_row(widget, 0, regular_item(gross=10, poly=1, purity=90.0, wage_rate=10.0))

        widget.toggle_return_mode()
        _set_row(
            widget, 1, return_item(gross=2.0, poly=0.5, purity=80.0, wage_rate=5.0)
        )
        widget.toggle_return_mode()

        widget.toggle_silver_bar_mode()
        _set_row(
            widget,
            2,
            silver_bar_item(gross=3.0, poly=0.0, purity=99.9, wage_rate=2.0),
        )
        widget.toggle_silver_bar_mode()

        assert widget._totals_incremental_is_active()

        widget.item_table.set_cell_text(0, COL_GROSS, "11.0")
        widget.handle_cell_changed(0, COL_GROSS)
        widget.item_table.set_cell_text(1, COL_GROSS, "2.5")
        widget.handle_cell_changed(1, COL_GROSS)
        widget.item_table.set_cell_text(2, COL_PURITY, "95.0")
        widget.handle_cell_changed(2, COL_PURITY)
        qtbot.waitUntil(
            lambda: float(widget.total_gross_label.text()) == pytest.approx(11.0),
            timeout=500,
        )

        assert float(widget.total_gross_label.text()) == pytest.approx(11.0)
        assert float(widget.return_gross_label.text()) == pytest.approx(2.5)
        assert float(widget.bar_gross_label.text()) == pytest.approx(3.0)
        assert float(widget.net_fine_label.text()) == pytest.approx(4.55, abs=0.01)
        assert float(widget.net_wage_label.text()) == pytest.approx(84.0, abs=0.01)
    finally:
        widget.deleteLater()


def test_incremental_rebuild_after_row_delete(qt_app, fake_db, monkeypatch):
    widget = _make_widget(fake_db)
    try:
        _set_row(
            widget, 0, regular_item(gross=5.0, poly=1.0, purity=90.0, wage_rate=10.0)
        )
        _set_row(
            widget, 1, regular_item(gross=4.0, poly=1.0, purity=90.0, wage_rate=10.0)
        )
        _set_row(
            widget, 2, regular_item(gross=3.0, poly=1.0, purity=90.0, wage_rate=10.0)
        )

        monkeypatch.setattr(
            "silverestimate.ui.estimate_entry_workflow_controller.QMessageBox.question",
            lambda *a, **k: QMessageBox.Yes,
            raising=False,
        )
        widget.item_table.setCurrentCell(1, COL_CODE)
        widget.delete_current_row()

        assert widget.item_table.rowCount() >= 2
        assert float(widget.total_gross_label.text()) == pytest.approx(8.0)
        assert float(widget.total_net_label.text()) == pytest.approx(6.0)
        assert float(widget.total_fine_label.text()) == pytest.approx(5.4, abs=0.01)
        assert len(widget._row_contrib_cache) == widget.item_table.rowCount()
    finally:
        widget.deleteLater()


def test_incremental_rebuild_after_apply_loaded_estimate(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        loaded = LoadedEstimate(
            voucher_no="V900",
            date="2026-02-14",
            silver_rate=0.0,
            note="",
            last_balance_silver=0.0,
            last_balance_amount=0.0,
            items=(
                SaveItem(
                    code="REG001",
                    row_number=1,
                    name="Regular",
                    gross=10.0,
                    poly=1.0,
                    net_wt=9.0,
                    purity=90.0,
                    wage_rate=10.0,
                    pieces=0,
                    wage=90.0,
                    fine=8.1,
                    is_return=False,
                    is_silver_bar=False,
                ),
                SaveItem(
                    code="RET001",
                    row_number=2,
                    name="Return",
                    gross=2.0,
                    poly=0.5,
                    net_wt=1.5,
                    purity=80.0,
                    wage_rate=0.0,
                    pieces=0,
                    wage=0.0,
                    fine=1.2,
                    is_return=True,
                    is_silver_bar=False,
                ),
            ),
        )

        assert widget.apply_loaded_estimate(loaded)
        assert float(widget.total_gross_label.text()) == pytest.approx(10.0)
        assert float(widget.return_gross_label.text()) == pytest.approx(2.0)
        assert float(widget.net_fine_label.text()) == pytest.approx(6.9, abs=0.01)
        assert len(widget._row_contrib_cache) == widget.item_table.rowCount()

        widget.item_table.set_cell_text(0, COL_GROSS, "12.0")
        widget.handle_cell_changed(0, COL_GROSS)
        _pump_events(160)

        assert float(widget.total_gross_label.text()) == pytest.approx(12.0)
        assert float(widget.net_fine_label.text()) == pytest.approx(8.7, abs=0.01)
    finally:
        widget.deleteLater()


def test_incremental_failure_does_not_use_legacy_fallback(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = _set_row(
            widget,
            0,
            regular_item(gross=10, poly=1, purity=92.5, wage_rate=10.0),
        )
        assert widget._totals_incremental_is_active()

        def _boom(_row_state):
            raise RuntimeError("forced incremental failure")

        widget._row_contribution_from_row_state = _boom
        table.set_cell_text(0, COL_GROSS, "11.0")
        widget.handle_cell_changed(0, COL_GROSS)
        _pump_events(160)

        assert widget._incremental_totals_failed is True
        assert float(widget.total_gross_label.text()) == pytest.approx(10.0)

        widget.item_table.set_cell_text(0, COL_GROSS, "12.0")
        widget.handle_cell_changed(0, COL_GROSS)
        _pump_events(160)
        assert float(widget.total_gross_label.text()) == pytest.approx(10.0)
        assert float(widget.net_wage_label.text()) == pytest.approx(90.0)
    finally:
        widget.deleteLater()


def test_widget_save_and_reload(qt_app, tmp_path, settings_stub, monkeypatch):
    db_path = tmp_path / "ui" / "estimate.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    manager = DatabaseManager(str(db_path), "test-pass")

    manager.items_repo.add_item("REG001", "Regular", 92.5, "WT", 10)
    manager.items_repo.add_item("RET001", "Return", 80.0, "WT", 0)
    manager.items_repo.add_item("BAR001", "Bar", 99.9, "WT", 0)

    widget = _make_widget(manager)
    widget.voucher_edit.setText("SAVE01")

    _set_row(widget, 0, regular_item(gross=10, poly=1, purity=92.5, wage_rate=10))

    widget.toggle_return_mode()
    _set_row(widget, 1, return_item(gross=1.5, poly=0.3, purity=75.0, wage_rate=0))
    widget.toggle_return_mode()

    widget.toggle_silver_bar_mode()
    _set_row(widget, 2, silver_bar_item(gross=2.0, poly=0.0, purity=99.9, wage_rate=0))
    widget.toggle_silver_bar_mode()

    from PyQt5.QtWidgets import QMessageBox as _QtMessageBox

    class _MsgBoxStub:
        Yes = _QtMessageBox.Yes
        No = _QtMessageBox.No
        Ok = _QtMessageBox.Ok

        @staticmethod
        def warning(*args, **kwargs):
            return _QtMessageBox.Ok

        @staticmethod
        def information(*args, **kwargs):
            return _QtMessageBox.Ok

        @staticmethod
        def critical(*args, **kwargs):
            return _QtMessageBox.Ok

        @staticmethod
        def question(*args, **kwargs):
            return _QtMessageBox.Yes

    # Patch the correct QMessageBox
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry_workflow_controller.QMessageBox",
        _MsgBoxStub,
        raising=False,
    )

    widget.print_estimate = lambda: None
    widget.save_estimate()

    widget_loaded = _make_widget(manager)
    widget_loaded.voucher_edit.setText("SAVE01")
    widget_loaded.safe_load_estimate()

    table = widget_loaded.item_table
    rows = []
    for row in range(table.rowCount()):
        code_text = table.get_cell_text(row, COL_CODE).strip()
        if code_text:
            rows.append((code_text, table.get_cell_text(row, COL_TYPE)))

    assert rows == [
        ("REG001", "Regular"),
        ("BAR001", "Silver Bar"),
        ("RET001", "Return"),
    ]

    assert float(table.get_cell_text(0, COL_NET_WT)) == pytest.approx(9.0)
    assert float(table.get_cell_text(1, COL_NET_WT)) == pytest.approx(2.0)
    assert float(table.get_cell_text(2, COL_NET_WT)) == pytest.approx(1.2)

    widget.deleteLater()
    widget_loaded.deleteLater()
    manager.close()


def test_print_estimate_uses_current_unsaved_state(qt_app, fake_db, monkeypatch):
    widget = _make_widget(fake_db)
    captured = {}

    class _PrintManagerStub:
        def __init__(self, db_manager, print_font=None):
            captured["db_manager"] = db_manager
            captured["print_font"] = print_font

    monkeypatch.setattr(
        "silverestimate.ui.print_manager.PrintManager",
        _PrintManagerStub,
    )

    def _capture_start(*, print_manager, voucher_no, estimate_data):
        captured["print_manager"] = print_manager
        captured["voucher_no"] = voucher_no
        captured["estimate_data"] = estimate_data

    widget._start_estimate_print_preview_build = _capture_start
    widget.voucher_edit.setText("LIVE001")
    widget.date_edit.setDate(QDate(2026, 2, 14))
    widget.note_edit.setText("Unsaved note")
    _set_row(
        widget,
        0,
        regular_item(gross=10, poly=1, purity=92.5, wage_rate=10),
    )

    widget.print_estimate()

    header = captured["estimate_data"]["header"]
    item = captured["estimate_data"]["items"][0]

    assert captured["db_manager"] is fake_db
    assert captured["voucher_no"] == "LIVE001"
    assert header["voucher_no"] == "LIVE001"
    assert header["date"] == "2026-02-14"
    assert header["note"] == "Unsaved note"
    assert item["item_code"] == "REG001"
    assert item["item_name"] == "Regular Item"
    assert item["is_return"] == 0
    assert item["is_silver_bar"] == 0

    widget.deleteLater()


def test_toggle_modes_updates_empty_row(qt_app, fake_db):
    widget = _make_widget(fake_db)
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.get_cell_text(last_row, COL_TYPE) == "Regular"
    widget.toggle_return_mode()
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.get_cell_text(last_row, COL_TYPE) == "Return"
    widget.toggle_silver_bar_mode()
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.get_cell_text(last_row, COL_TYPE) == "Silver Bar"
    widget.toggle_silver_bar_mode()
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.get_cell_text(last_row, COL_TYPE) == "Regular"


def test_populate_row_updates_code_cell(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        if table.rowCount() == 0:
            widget.add_empty_row()

        table.set_cell_text(0, COL_CODE, "old-code")
        widget.populate_row(
            0,
            {"code": "new123", "name": "New Item", "purity": 91.6, "wage_rate": 10.0},
        )

        assert table.get_cell_text(0, COL_CODE) == "NEW123"
        assert table.get_cell_text(0, COL_ITEM_NAME) == "New Item"
        assert table.get_row_state(0).code == "NEW123"
    finally:
        widget.deleteLater()


def test_prompt_item_selection_uses_widget_parent(qt_app, fake_db, monkeypatch):
    widget = _make_widget(fake_db)
    captured = {}

    class _DialogStub:
        def __init__(self, db_manager, search_term, parent=None):
            captured["db_manager"] = db_manager
            captured["search_term"] = search_term
            captured["parent"] = parent

        def exec_(self):
            return QDialog.Accepted

        def get_selected_item(self):
            return {
                "code": "ALT001",
                "name": "Alt Item",
                "purity": 91.6,
                "wage_type": "WT",
                "wage_rate": 10.0,
            }

    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry_workflow_controller.ItemSelectionDialog",
        _DialogStub,
        raising=False,
    )

    try:
        picked = widget.prompt_item_selection("bad")

        assert captured["db_manager"] is fake_db
        assert captured["search_term"] == "bad"
        assert captured["parent"] is widget
        assert picked is not None
        assert picked["code"] == "ALT001"
    finally:
        widget.deleteLater()


def test_apply_loaded_estimate_normalizes_wt_pieces_to_zero(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        loaded = LoadedEstimate(
            voucher_no="V001",
            date="2026-02-14",
            silver_rate=100.0,
            note="",
            last_balance_silver=0.0,
            last_balance_amount=0.0,
            items=(
                SaveItem(
                    code="WT001",
                    row_number=1,
                    name="WT Item",
                    gross=10.0,
                    poly=1.0,
                    net_wt=9.0,
                    purity=92.5,
                    wage_rate=10.0,
                    pieces=7,
                    wage=90.0,
                    fine=8.33,
                    is_return=False,
                    is_silver_bar=False,
                ),
            ),
        )

        assert widget.apply_loaded_estimate(loaded)
        table = widget.item_table
        assert table.get_cell_text(0, COL_PIECES) == "0"
        pieces_index = table.get_model().index(0, COL_PIECES)
        assert not bool(table.get_model().flags(pieces_index) & Qt.ItemIsEditable)
    finally:
        widget.deleteLater()


def test_totals_position_switching_and_persistence(qt_app, fake_db, settings_stub):
    widget = _make_widget(fake_db)
    try:
        splitter = widget._content_splitter
        assert splitter.orientation() == Qt.Horizontal

        widget._apply_totals_position("left")
        assert splitter.orientation() == Qt.Horizontal
        assert splitter.widget(0) is widget.totals_panel
        assert (
            widget._settings().value("ui/estimate_totals_position", type=str) == "left"
        )

        widget._on_totals_position_requested("bottom")
        assert splitter.orientation() == Qt.Vertical
        assert splitter.widget(1) is widget.totals_panel
        assert (
            widget._settings().value("ui/estimate_totals_position", type=str)
            == "bottom"
        )

        widget._on_totals_position_requested("right")
        assert splitter.orientation() == Qt.Horizontal
        assert splitter.widget(1) is widget.totals_panel
        assert (
            widget._settings().value("ui/estimate_totals_position", type=str) == "right"
        )
    finally:
        widget.deleteLater()


def test_live_rate_card_moves_between_sidebar_and_header(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        sidebar_top_host = widget._totals_panel_sidebar._sidebar_top_host

        assert widget.secondary_actions.live_rate_container.parent() is sidebar_top_host
        assert not sidebar_top_host.isHidden()

        widget._apply_totals_position("bottom")
        qt_app.processEvents()

        assert widget.secondary_actions.live_rate_container.parent() is widget.secondary_actions
        assert not widget.secondary_actions.live_rate_divider.isHidden()

        widget._apply_totals_position("right")
        qt_app.processEvents()

        assert widget.secondary_actions.live_rate_container.parent() is sidebar_top_host
        assert widget.secondary_actions.live_rate_divider.isHidden()
    finally:
        widget.deleteLater()


def test_compact_header_preserves_table_viewport_height(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        widget.resize(1280, 800)
        widget.show()
        qt_app.processEvents()

        header_container = _find_named_widget(widget, "EstimateHeaderContainer")
        assert header_container is not None
        assert header_container.height() <= 60
        assert widget.mode_indicator_label.isVisible()
        assert widget.item_table.viewport().height() >= 694
    finally:
        widget.deleteLater()


def test_totals_section_order_sync_and_persistence(qt_app, fake_db, settings_stub):
    widget = _make_widget(fake_db)
    try:
        new_order = ["silver_bar", "return", "regular", "totals"]
        expected_order = TotalsPanel.normalize_section_order(new_order)
        widget._apply_totals_section_order(new_order, persist=True)

        assert widget._totals_panel_sidebar.section_order() == expected_order
        assert widget._totals_panel_bottom.section_order() == expected_order
        assert widget._settings().value(
            "ui/estimate_totals_section_order", type=str
        ) == ",".join(expected_order)

        widget_loaded = _make_widget(fake_db)
        try:
            assert widget_loaded._totals_panel_sidebar.section_order() == expected_order
            assert widget_loaded._totals_panel_bottom.section_order() == expected_order
        finally:
            widget_loaded.deleteLater()
    finally:
        widget.deleteLater()


def test_column_width_auto_fits_content_expand_and_shrink(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        col = COL_ITEM_NAME

        table.set_cell_text(0, col, "A")
        widget._schedule_columns_autofit([col], delay_ms=0, force=True)
        widget._apply_pending_column_autofit()
        base_width = table.columnWidth(col)

        table.set_cell_text(
            0, col, "Very Long Item Name For Dynamic Width Testing 12345"
        )
        widget._schedule_columns_autofit([col], delay_ms=0, force=True)
        widget._apply_pending_column_autofit()
        expanded_width = table.columnWidth(col)

        table.set_cell_text(0, col, "AB")
        widget._schedule_columns_autofit([col], delay_ms=0, force=True)
        widget._apply_pending_column_autofit()
        shrink_width = table.columnWidth(col)

        assert expanded_width > base_width
        assert shrink_width < expanded_width
    finally:
        widget.deleteLater()


def test_column_autofit_defaults_to_explicit_mode(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        col = COL_ITEM_NAME
        widget._pending_autofit_columns.clear()
        widget._schedule_columns_autofit([col], delay_ms=0)
        assert col not in widget._pending_autofit_columns
    finally:
        widget.deleteLater()


def test_non_autofit_uses_native_stretch_for_item_name(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        header = widget.item_table.horizontalHeader()
        assert header.sectionResizeMode(COL_ITEM_NAME) == QHeaderView.Stretch
        assert header.sectionResizeMode(COL_CODE) == QHeaderView.Interactive
    finally:
        widget.deleteLater()


def test_non_autofit_persists_fixed_column_widths_only(qt_app, fake_db, settings_stub):
    widget = _make_widget(fake_db)
    try:
        widget.item_table.setColumnWidth(COL_CODE, 137)
        widget._save_column_widths_setting()
        saved = widget._settings().value("ui/estimate_table_column_widths", type=str)
        assert saved is not None
        tokens = [int(token) for token in saved.split(",")]
        assert tokens[COL_CODE] == 137
        assert tokens[COL_ITEM_NAME] == -1

        widget_reloaded = _make_widget(fake_db)
        try:
            header = widget_reloaded.item_table.horizontalHeader()
            assert header.sectionResizeMode(COL_ITEM_NAME) == QHeaderView.Stretch
            assert widget_reloaded.item_table.columnWidth(COL_CODE) == 137
        finally:
            widget_reloaded.deleteLater()
    finally:
        widget.deleteLater()


def test_non_autofit_expands_fixed_column_when_edit_content_grows(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        base_width = table.columnWidth(COL_CODE)

        table.set_cell_text(0, COL_CODE, "LONG-CODE-123456789")
        widget.handle_cell_changed(0, COL_CODE)
        widget._ensure_column_can_fit_content(COL_CODE)

        assert table.columnWidth(COL_CODE) > base_width
    finally:
        widget.deleteLater()


def test_numeric_cell_editor_is_right_aligned_and_selects_text(qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        widget.item_table.set_cell_text(0, COL_GROSS, "1234567.5")
        assert widget.item_table.get_cell_text(0, COL_GROSS) == "12,34,567.500"
        widget.item_table.setCurrentCell(0, COL_GROSS)
        assert widget.item_table.begin_cell_edit(0, COL_GROSS)
        qtbot.waitUntil(
            lambda: widget.item_table.findChild(QLineEdit) is not None, timeout=1000
        )
        editor = widget.item_table.findChild(QLineEdit)
        assert editor is not None
        model_font = widget.item_table.get_model().data(
            widget.item_table.get_model().index(0, COL_GROSS), Qt.FontRole
        )
        assert model_font is not None
        assert bool(editor.alignment() & Qt.AlignRight)
        assert editor.font().key() == model_font.key()
        assert editor.text() == "1234567.5"
        assert editor.selectedText() == "1234567.5"
    finally:
        widget.deleteLater()


def test_numeric_helpers_read_raw_values_when_display_is_grouped(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        table.set_cell_text(0, COL_GROSS, "1234567.5")
        table.set_cell_text(0, COL_PIECES, "123456")

        assert table.get_cell_text(0, COL_GROSS) == "12,34,567.500"
        assert table.get_cell_text(0, COL_PIECES) == "1,23,456"
        assert widget._get_cell_float(0, COL_GROSS) == pytest.approx(1234567.5)
        assert widget._get_cell_int(0, COL_PIECES) == 123456
    finally:
        widget.deleteLater()


def test_table_edit_pipeline_invokes_handle_cell_changed_once(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        calls = []
        widget.handle_cell_changed = lambda row, col: calls.append((row, col))
        model = widget.item_table.get_model()
        index = model.index(0, COL_GROSS)
        assert model.setData(index, "12.5", Qt.EditRole)
        assert calls == [(0, COL_GROSS)]
    finally:
        widget.deleteLater()


def test_calculate_wage_uses_row_wage_type_without_repository_lookup(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        if table.rowCount() == 0:
            widget.add_empty_row()

        repo_calls = []
        fake_db.get_item_by_code = lambda code: (
            repo_calls.append(code)
            or {
                "wage_type": "WT",
                "wage_rate": 1.0,
            }
        )

        model = table.get_model()
        model.set_row_wage_type(0, "PC")

        table.set_cell_text(0, COL_CODE, "PC001")
        table.set_cell_text(0, COL_GROSS, "10")
        table.set_cell_text(0, COL_POLY, "2")
        table.set_cell_text(0, COL_PURITY, "90")
        table.set_cell_text(0, COL_WAGE_RATE, "5")
        table.set_cell_text(0, COL_PIECES, "3")

        widget.current_row = 0
        widget.calculate_wage()

        assert float(table.get_cell_text(0, COL_WAGE_AMT)) == pytest.approx(15.0)
        assert repo_calls == []
    finally:
        widget.deleteLater()


def test_totals_recalc_is_debounced(qt_app, qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        calls = []
        original_apply = widget.apply_totals

        def _capture_apply(totals):
            calls.append(totals)
            original_apply(totals)

        widget.apply_totals = _capture_apply  # type: ignore[method-assign]
        _pump_events(40)
        calls.clear()

        widget._schedule_totals_recalc(delay_ms=10)
        widget._schedule_totals_recalc(delay_ms=10)
        widget._schedule_totals_recalc(delay_ms=10)
        qtbot.waitUntil(lambda: len(calls) == 1, timeout=500)

        assert len(calls) == 1
    finally:
        widget.deleteLater()
