from PyQt5.QtGui import QFont
from PyQt5.QtPrintSupport import QPrinter

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.print_manager import PrintManager
from silverestimate.ui.print_payload_builder import PrintPreviewPayload


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


def test_generate_estimate_new_format_keeps_final_totals_to_one_decimal(
    qt_app, settings_stub
):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    estimate_data = {
        "header": {
            "voucher_no": "V-001",
            "date": "2026-02-13",
            "silver_rate": 10.1,
            "note": "",
            "last_balance_silver": 0.0,
            "last_balance_amount": 0.0,
        },
        "items": [
            {
                "item_name": "Chain",
                "gross": 1.5,
                "poly": 0.0,
                "net_wt": 1.5,
                "purity": 92.5,
                "wage_rate": 0.0,
                "pieces": 1,
                "fine": 1.23,
                "wage": 100.2,
                "is_return": 0,
                "is_silver_bar": 0,
            }
        ],
    }

    rendered = manager._generate_estimate_new_format(estimate_data)

    assert "S.Cost : Rs. 12.4" in rendered
    assert "Total: Rs. 112.6" in rendered


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
    manager._generate_estimate_old_format = lambda data: "OLD"
    manager._generate_estimate_new_format = lambda data: "NEW"
    manager._generate_estimate_thermal_format = lambda data: "THERMAL"

    payload = manager.build_estimate_preview_payload(
        "V-002",
        estimate_data=estimate_data,
    )

    assert payload is not None
    assert payload.html_content == "THERMAL"
    assert payload.title == "Print Preview - Estimate V-002"
    assert payload.table_mode is False
    assert payload.document_kind == "estimate"
    assert payload.identifier == "V-002"
    assert payload.suggested_filename == "Estimate-V-002.pdf"
    assert payload.layout_mode == "thermal"
    assert payload.available_layouts == ("old", "new", "thermal")

    switched = payload.layout_factory("new")
    assert switched is not None
    assert switched.html_content == "NEW"
    assert switched.layout_mode == "new"


def test_show_preview_delegates_to_preview_dialog(qt_app, settings_stub):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    calls = []

    manager._preview_controller.open_preview = lambda payload, parent_widget=None: (
        calls.append((payload, parent_widget))
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

    assert calls == [(payload, "parent")]


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
    assert payload.suggested_filename == "Silver-Bar-List-LIST-010.pdf"


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
    assert payload.suggested_filename == "Silver-Bar-Inventory.pdf"


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


def test_print_manager_migrates_legacy_portrait_default_to_landscape(
    qt_app, settings_stub
):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("print/orientation", "Portrait")

    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))

    assert manager.printer.orientation() == QPrinter.Landscape
    assert settings.value("print/orientation") == "Landscape"


def test_print_manager_preserves_explicit_portrait_orientation(qt_app, settings_stub):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("print/orientation", "Portrait")
    settings.setValue("print/orientation_explicit", True)

    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))

    assert manager.printer.orientation() == QPrinter.Portrait


def test_print_manager_uses_persisted_custom_page_size(qt_app, settings_stub):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("print/page_size", "Counter Slip")
    settings.setValue("print/page_size_name", "Counter Slip")
    settings.setValue("print/page_width_mm", 120.0)
    settings.setValue("print/page_height_mm", 190.0)

    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    page_size = manager.printer.pageLayout().pageSize()

    assert page_size.name() == "Counter Slip"
    assert page_size.size(page_size.Millimeter).width() == 120.0
    assert page_size.size(page_size.Millimeter).height() == 190.0


def test_preview_layout_changes_become_default_for_next_estimate_preview(
    qt_app, settings_stub
):
    del qt_app, settings_stub
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    estimate_data = {
        "header": {
            "voucher_no": "V-004",
            "date": "2026-02-13",
            "silver_rate": 0.0,
            "note": "",
            "last_balance_silver": 0.0,
            "last_balance_amount": 0.0,
        },
        "items": [],
    }

    manager._preview_controller._save_preview_defaults(
        PrintPreviewPayload(
            html_content="THERMAL",
            title="Print Preview - Estimate V-004",
            document_kind="estimate",
            identifier="V-004",
            suggested_filename="Estimate-V-004.pdf",
            layout_mode="thermal",
            available_layouts=("old", "new", "thermal"),
        )
    )
    payload = manager.build_estimate_preview_payload(
        "V-004",
        estimate_data=estimate_data,
    )

    assert payload is not None
    assert manager.estimate_layout_mode == "thermal"
    assert payload.layout_mode == "thermal"
