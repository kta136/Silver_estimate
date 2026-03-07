from PyQt5.QtGui import QFont

from silverestimate.ui.print_manager import PrintManager


class _DbStub:
    pass


def test_generate_silver_bars_html_escapes_dynamic_text(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    bars = [
        {
            "bar_id": 1,
            "estimate_voucher_no": "V1<script>alert(1)</script>",
            "weight": 12.345,
            "purity": 99.99,
            "fine_weight": 12.343,
            "date_added": "2026-02-13 <today>",
            "status": "In <Stock>",
        }
    ]

    rendered = manager._generate_silver_bars_html_table(bars, status_filter="<all>")

    assert "<script>alert(1)</script>" not in rendered
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "In &lt;Stock&gt;" in rendered
    assert "2026-02-13 &lt;today&gt;" in rendered
    assert "SILVER BARS INVENTORY - &lt;all&gt;" in rendered


def test_generate_estimate_thermal_escapes_note_html(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    estimate_data = {
        "header": {
            "voucher_no": "V-001",
            "date": "2026-02-13",
            "silver_rate": 0.0,
            "note": "<b>unsafe-note</b>",
            "last_balance_silver": 0.0,
            "last_balance_amount": 0.0,
        },
        "items": [],
    }

    rendered = manager._generate_estimate_thermal_format(estimate_data)

    assert "<b>unsafe-note</b>" not in rendered
    assert "&lt;b&gt;unsafe-note&lt;/b&gt;" in rendered


def test_build_estimate_preview_payload_uses_selected_layout(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    estimate_data = {
        "header": {
            "voucher_no": "V-002",
            "date": "2026-02-13",
            "silver_rate": 0.0,
            "note": "",
            "last_balance_silver": 0.0,
            "last_balance_amount": 0.0,
        },
        "items": [],
    }

    manager.estimate_layout_mode = "thermal"
    manager._generate_estimate_thermal_format = lambda data: "THERMAL"

    payload = manager.build_estimate_preview_payload(
        "V-002",
        estimate_data=estimate_data,
    )

    assert payload is not None
    assert payload.html_content == "THERMAL"
    assert payload.title == "Print Preview - Estimate V-002"
    assert payload.table_mode is False


def test_show_preview_delegates_to_preview_dialog(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    calls = []

    manager._preview_controller.open_preview = (
        lambda html_content, parent_widget, title, table_mode=False: calls.append(
            (html_content, parent_widget, title, table_mode)
        )
    )

    payload = manager.build_estimate_preview_payload(
        "V-003",
        estimate_data={
            "header": {
                "voucher_no": "V-003",
                "date": "2026-02-13",
                "silver_rate": 0.0,
                "note": "",
                "last_balance_silver": 0.0,
                "last_balance_amount": 0.0,
            },
            "items": [],
        },
    )
    assert payload is not None

    manager.show_preview(payload, parent_widget="parent")

    assert calls == [(payload.html_content, "parent", payload.title, False)]


def test_build_silver_bar_list_preview_payload_marks_table_mode(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    manager._generate_list_details_html = lambda info, bars: "LIST-HTML"

    payload = manager.build_silver_bar_list_preview_payload(
        {"list_identifier": "LIST-010"},
        [{"bar_id": 1}],
    )

    assert payload is not None
    assert payload.html_content == "LIST-HTML"
    assert payload.title == "Print Preview - List LIST-010"
    assert payload.table_mode is True


def test_build_silver_bar_inventory_preview_payload_marks_table_mode(
    qt_app, settings_stub
):
    class _InventoryDbStub:
        @staticmethod
        def get_silver_bars(status_filter):
            assert status_filter == "AVAILABLE"
            return [{"bar_id": 1}]

    manager = PrintManager(_InventoryDbStub(), print_font=QFont("Courier New", 8))
    manager._generate_silver_bars_html_table = lambda bars, status_filter: (
        f"INVENTORY-{status_filter}-{len(bars)}"
    )

    payload = manager.build_silver_bar_inventory_preview_payload("AVAILABLE")

    assert payload is not None
    assert payload.html_content == "INVENTORY-AVAILABLE-1"
    assert payload.title == "Print Preview - Silver Bar Inventory"
    assert payload.table_mode is True


def test_generate_list_details_html_escapes_list_note(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))

    rendered = manager._generate_list_details_html(
        {
            "list_identifier": 'LIST-011<script>alert("x")</script>',
            "list_note": "<b>fragile</b>",
        },
        [
            {
                "weight": 10.5,
                "purity": 99.9,
                "fine_weight": 10.49,
            }
        ],
    )

    assert '<script>alert("x")</script>' not in rendered
    assert "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in rendered
    assert "<b>fragile</b>" not in rendered
    assert "&lt;b&gt;fragile&lt;/b&gt;" in rendered
