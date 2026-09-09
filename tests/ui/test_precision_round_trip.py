"""Exercise rounding from real entry calculations through encrypted saves and print."""

from dataclasses import replace

import pytest

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.estimate_print_layout import build_modern_estimate_layout
from silverestimate.ui.view_models import EstimateEntryRowState
from tests.factories import estimate_totals, regular_item


@pytest.fixture
def precision_db(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "precision.db"), "test-pass", device_secret=b"P" * 32
    )
    assert db.add_item("REG001", "Precision", 92.5, "WT", 1)
    yield db
    db.close()


@pytest.mark.parametrize("category", list(EstimateLineCategory))
def test_purity_above_100_survives_calculation_save_inventory_and_print(
    qtbot, precision_db, make_estimate_widget, category
):
    db = precision_db
    assert db.update_item("REG001", "High Tunch", 125.5, "WT", 1, tunch="125.50%")
    widget = make_estimate_widget(db)
    widget.voucher_edit.setText("HIGH")
    widget.item_table.replace_all_rows(
        [
            EstimateEntryRowState(
                code="REG001",
                name="High Tunch",
                gross=10,
                purity=125.5,
                wage_rate=1,
                category=category,
                line_key="high-tunch",
            )
        ]
    )
    widget.totals_controller._recompute_row_derived_values(0, schedule_totals=False)
    widget.totals_controller.calculate_totals()
    assert widget.item_table.get_all_rows()[0].fine_weight == 12.55
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    saved = db.get_estimate_by_voucher("HIGH")
    assert saved["items"][0]["purity"] == 125.5
    assert saved["items"][0]["fine"] == 12.55
    assert saved["items"][0]["tunch"] == "125.50%"
    if category == EstimateLineCategory.SILVER_BAR:
        bar = db.silver_bar_query_repo.get_silver_bars_for_estimate("HIGH")[0]
        assert bar["purity"] == 125.5
        assert bar["fine_weight"] == 12.55
    document = EstimatePrintDocument.from_mapping(saved, show_tunch=True)
    printed = build_modern_estimate_layout(document).normalized_text()
    assert "125.50%" in printed and "125.50" in printed and "12.55" in printed
    assert widget.workflow_controller.apply_loaded_estimate(
        widget.presenter.load_estimate("HIGH")
    )
    widget.note_edit.setText("Preserve high Tunch")
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    reloaded = db.get_estimate_by_voucher("HIGH")
    assert reloaded["items"][0]["purity"] == 125.5
    assert reloaded["items"][0]["fine"] == 12.55


def test_entry_save_inventory_history_and_print_agree(
    qtbot, precision_db, make_estimate_widget
):
    db = precision_db
    widget = make_estimate_widget(db)
    widget.voucher_edit.setText("1")
    regular = EstimateEntryRowState(
        code="REG001",
        name="Precision",
        gross=10.125,
        purity=92.5,
        wage_rate=1,
        line_key="one",
    )
    widget.item_table.replace_all_rows(
        [
            regular,
            replace(regular, line_key="two"),
            replace(
                regular,
                line_key="return",
                gross=1.001,
                purity=50,
                wage_rate=0,
                category=EstimateLineCategory.RETURN,
            ),
            replace(
                regular,
                line_key="bar",
                wage_rate=0,
                category=EstimateLineCategory.SILVER_BAR,
            ),
        ]
    )
    for i in range(4):
        widget.totals_controller._recompute_row_derived_values(i, schedule_totals=False)
    widget.last_balance_silver = -0.005
    widget.last_balance_amount = -1.25
    widget.silver_rate_spin.setValue(12.34)
    widget.totals_controller.calculate_totals()
    rows = widget.item_table.get_all_rows()
    assert [(row.net_weight, row.fine_weight, row.wage_amount) for row in rows] == [
        (10.13, 9.37, 10.13),
        (10.13, 9.37, 10.13),
        (1.00, 0.50, 0),
        (10.13, 9.37, 0),
    ]
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    saved = db.get_estimate_by_voucher("1")
    bar = db.silver_bar_query_repo.get_silver_bars_for_estimate("1")[0]
    assert bar["fine_weight"] == 9.37
    assert saved["header"]["total_fine"] == 8.87
    from silverestimate.domain.estimate_totals import calculate_grand_total

    history = db.get_estimate_history_rows()[0]
    assert (
        calculate_grand_total(
            net_fine=history["total_fine"],
            net_wage=history["total_wage"],
            silver_rate=history["silver_rate"],
            last_balance_silver=history["last_balance_silver"],
            last_balance_amount=history["last_balance_amount"],
        )
        == 128.40
    )
    document = EstimatePrintDocument.from_mapping(saved)
    modern = build_modern_estimate_layout(document)
    assert modern.fine_weight == "8.87"
    metrics = {metric.label: metric.value for metric in modern.final_metrics}
    assert metrics == {
        "Total Lbr Amt (₹)": "19.01",
        "Silver Value (₹)": "109.39",
        "GRAND TOTAL (₹)": "128.40",
    }
    assert widget.workflow_controller.apply_loaded_estimate(
        widget.presenter.load_estimate("1")
    )
    reloaded = widget.item_table.get_all_rows()
    assert {
        row.line_key: (row.fine_weight, row.wage_amount) for row in reloaded if row.code
    } == {row.line_key: (row.fine_weight, row.wage_amount) for row in rows}


def test_loading_printing_and_note_only_save_preserve_legacy_line_amounts(
    qtbot, precision_db, make_estimate_widget
):
    db = precision_db
    line = regular_item(
        gross=10.125, net_wt=10.125, fine=9.365625, wage=10.125, line_key="legacy"
    )
    assert db.save_estimate_with_returns(
        "old",
        "2026-09-05",
        12.34,
        [line],
        [],
        estimate_totals(net_fine=9.365625, net_wage=10.125),
    )
    before = db.get_estimate_by_voucher("old")
    widget = make_estimate_widget(db)
    assert widget.workflow_controller.apply_loaded_estimate(
        widget.presenter.load_estimate("old")
    )
    row = widget.item_table.get_all_rows()[0]
    assert row.fine_weight == 9.365625 and row.wage_amount == 10.125
    document = EstimatePrintDocument.from_mapping(before)
    build_modern_estimate_layout(document)
    assert db.get_estimate_by_voucher("old") == before
    widget.note_edit.setText("Note changed")
    assert widget.workflow_controller.save_estimate(continue_editing=True)
    saved = db.get_estimate_by_voucher("old")
    for field in ("gross", "poly", "net_wt", "purity", "wage_rate", "fine", "wage"):
        assert saved["items"][0][field] == before["items"][0][field]


def test_balance_dialog_rounds_signed_weights_to_two_decimals(
    qtbot, precision_db, make_estimate_widget, monkeypatch
):
    from PySide6.QtWidgets import QDialog

    from silverestimate.ui.themed_controls import ThemedDoubleSpinBox

    widget = make_estimate_widget(precision_db)
    widget.last_balance_silver = -0.005
    widget.last_balance_amount = -1.25

    def accept(dialog):
        fields = dialog.findChildren(ThemedDoubleSpinBox)
        assert [(field.decimals(), field.value()) for field in fields] == [
            (2, -0.01),
            (2, -1.25),
        ]
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept)
    widget.workflow_controller.show_last_balance_dialog()
    assert widget.last_balance_silver == -0.01
    assert widget.last_balance_amount == -1.25
