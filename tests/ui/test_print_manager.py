import os
import sqlite3
from copy import deepcopy
from pathlib import Path

from PyQt6.QtCore import QMarginsF, QSizeF
from PyQt6.QtGui import QFont, QFontDatabase, QPageLayout, QPageSize
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPrintSupport import QPrinter

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.print_manager import PrintManager
from silverestimate.ui.print_payload_builder import HtmlPrintDocument
from tests.factories import multi_section_print_estimate


class _DbStub:
    pass


def _modern_layout(manager: PrintManager, estimate_data):
    document = EstimatePrintDocument.from_mapping(estimate_data)
    return manager._estimate_renderer.build_modern_layout(document)


def _render_estimate_pdf(
    manager: PrintManager,
    estimate_data,
    output_path,
    *,
    page_layout: QPageLayout | None = None,
) -> None:
    _ensure_print_test_font()
    payload = manager.build_estimate_preview_payload(
        estimate_data["header"]["voucher_no"],
        estimate_data=estimate_data,
    )
    assert payload is not None
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output_path))
    printer.setPageLayout(page_layout or manager.printer.pageLayout())
    manager._render_document(printer, payload.document)


def _ensure_print_test_font() -> None:
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    font_dir = windows_dir / "Fonts"
    families = set(QFontDatabase.families())
    font_files = ()
    if "Arial" not in families:
        font_files += ("arial.ttf", "arialbd.ttf")
    if "Courier New" not in families:
        font_files += ("cour.ttf", "courbd.ttf")
    for filename in font_files:
        font_path = font_dir / filename
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))


def _pdf_pages(output_path) -> tuple[tuple[str, ...], QPdfDocument]:
    document = QPdfDocument(None)
    assert document.load(str(output_path)) == QPdfDocument.Error.None_
    pages = tuple(
        document.getAllText(index).text() for index in range(document.pageCount())
    )
    return pages, document


def _long_estimate_data(item_count: int = 60):
    estimate_data = multi_section_print_estimate()
    template = estimate_data["items"][0]
    rows = []
    for index in range(1, item_count + 1):
        item = deepcopy(template)
        item["item_code"] = f"LONG{index:03d}"
        item["item_name"] = f"Long Regular Item {index:03d} with descriptive name"
        rows.append(item)
    estimate_data["items"] = rows
    return estimate_data


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


def test_estimate_modern_layout_uses_requested_column_precision(qt_app, settings_stub):
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
                "gross": 12.34,
                "poly": 5.0,
                "net_wt": 7.34,
                "purity": 92.5,
                "wage_rate": 0.0,
                "pieces": 11,
                "fine": 1.23,
                "wage": 100.2,
                "is_return": 0,
                "is_silver_bar": 0,
            }
        ],
    }

    layout = _modern_layout(manager, estimate_data)
    lines = layout.lines
    rendered = layout.normalized_text()
    item_line = next(line for line in lines if "Chain" in line)
    total_line = next(line for line in lines if "TOTAL" in line)
    final_line = next(line for line in lines if "Fine Silver:" in line)

    assert "12.34" in item_line
    assert "5.00" in item_line
    assert "7.34" in item_line
    assert "92.50" in item_line
    assert "11" in item_line
    assert "1.23" in item_line
    assert item_line.rstrip().endswith("100")

    assert "12.34" in total_line
    assert "5.00" in total_line
    assert "7.34" in total_line
    assert "1.23" in total_line
    assert total_line.rstrip().endswith("100")

    assert "Fine Silver: 1.23 g" in final_line
    assert "100" in final_line
    assert "Silver Cost: Rs. 12.4" in rendered
    assert "Total: Rs. 112.6" in rendered


def test_estimate_modern_layout_keeps_amount_totals_at_one_decimal(
    qt_app, settings_stub
):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    estimate_data = {
        "header": {
            "voucher_no": "V-005",
            "date": "2026-02-13",
            "silver_rate": 10.1,
            "note": "",
            "last_balance_silver": 0.27,
            "last_balance_amount": 50.54,
        },
        "items": [
            {
                "item_name": "Chain",
                "gross": 1.54,
                "poly": 0.04,
                "net_wt": 1.5,
                "purity": 92.54,
                "wage_rate": 10.04,
                "pieces": 1,
                "fine": 1.23,
                "wage": 100.24,
                "is_return": 0,
                "is_silver_bar": 0,
            }
        ],
    }

    layout = _modern_layout(manager, estimate_data)
    lines = layout.lines
    rendered = layout.normalized_text()
    item_line = next(line for line in lines if "Chain" in line)
    total_line = next(line for line in lines if "TOTAL" in line)
    final_line = next(line for line in lines if "Fine Silver:" in line)

    assert "1.54" in item_line
    assert "0.04" in item_line
    assert "1.50" in item_line
    assert "92.54" in item_line
    assert "1" in item_line
    assert "1.23" in item_line
    assert item_line.rstrip().endswith("100")

    assert "1.54" in total_line
    assert "1.50" in total_line
    assert "1.23" in total_line
    assert total_line.rstrip().endswith("100")

    assert "Silver: 0.27 g | Amount: Rs. 50.5" in rendered
    assert "Fine Silver: 1.50 g" in final_line
    assert "Silver Cost: Rs. 15.1" in rendered
    assert "Total: Rs. 165.9" in rendered


def test_build_estimate_preview_payload_uses_modern_layout(qt_app, settings_stub):
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

    payload = manager.build_estimate_preview_payload(
        "V-002",
        estimate_data=estimate_data,
    )

    assert payload is not None
    assert isinstance(payload.document, EstimatePrintDocument)
    assert payload.document.header.voucher_no == "V-002"
    assert payload.document.format_key == "modern"
    assert payload.title == "Print Preview - Estimate V-002"
    assert payload.document_kind == "estimate"
    assert payload.identifier == "V-002"
    assert payload.suggested_filename == "Estimate-V-002.pdf"
    assert payload.format_key == "modern"
    assert payload.available_formats == ("classic", "modern")
    assert payload.format_factory is not None

    classic_payload = payload.format_factory("classic")

    assert classic_payload is not None
    assert isinstance(classic_payload.document, EstimatePrintDocument)
    assert classic_payload.document.format_key == "classic"
    assert classic_payload.format_key == "classic"


def test_estimate_payload_uses_remembered_tunch_visibility(qt_app, settings_stub):
    get_app_settings().setValue("print/show_tunch", True)
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    estimate_data = {
        "header": {
            "voucher_no": "V-TUNCH",
            "date": "2026-07-19",
            "silver_rate": 0.0,
        },
        "items": [],
    }

    payload = manager.build_estimate_preview_payload(
        "V-TUNCH",
        estimate_data=estimate_data,
    )

    assert payload is not None
    assert payload.show_tunch is True
    assert payload.document.show_tunch is True
    assert payload.tunch_visibility_factory is not None

    hidden_payload = payload.tunch_visibility_factory(False)
    assert hidden_payload is not None
    assert hidden_payload.show_tunch is False
    assert hidden_payload.document.show_tunch is False
    assert hidden_payload.format_factory is not None
    hidden_classic = hidden_payload.format_factory("classic")
    assert hidden_classic is not None
    assert hidden_classic.show_tunch is False
    assert hidden_classic.document.show_tunch is False


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
    assert isinstance(payload.document, HtmlPrintDocument)
    assert payload.document.html_content == "LIST-HTML"
    assert payload.title == "Print Preview - List LIST-010"
    assert payload.document.table_mode is True
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
    assert isinstance(payload.document, HtmlPrintDocument)
    assert payload.document.html_content == "INVENTORY-AVAILABLE-1"
    assert payload.title == "Print Preview - Silver Bar Inventory"
    assert payload.document.table_mode is True
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


def test_generate_list_details_html_reads_values_from_sqlite_rows(
    qt_app, settings_stub
):
    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        bar = connection.execute(
            "SELECT 12.5 AS weight, 99.2 AS purity, 12.4 AS fine_weight"
        ).fetchone()

        rendered = manager._generate_list_details_html(
            {"list_identifier": "LIST-012", "list_note": "SQLite row"},
            [bar],
        )
    finally:
        connection.close()

    assert "12.500" in rendered
    assert "99.20" in rendered
    assert "12.400" in rendered
    assert "TOTAL Weight: 12.500 g" in rendered
    assert "TOTAL Fine Wt: 12.400 g" in rendered


def test_print_manager_preserves_portrait_orientation(qt_app, settings_stub):
    del qt_app, settings_stub
    settings = get_app_settings()
    settings.setValue("print/orientation", "Portrait")

    manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))

    assert (
        manager.printer.pageLayout().orientation() == QPageLayout.Orientation.Portrait
    )


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
    assert page_size.size(QPageSize.Unit.Millimeter).width() == 120.0
    assert page_size.size(QPageSize.Unit.Millimeter).height() == 190.0


def test_legacy_layout_settings_migrate_to_classic_or_modern(qt_app, settings_stub):
    del qt_app, settings_stub
    settings = get_app_settings()
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

    settings.setValue("print/estimate_layout", "old")
    classic_manager = PrintManager(_DbStub(), print_font=QFont("Courier New", 8))
    classic_payload = classic_manager.build_estimate_preview_payload(
        "V-004",
        estimate_data=estimate_data,
    )
    settings.setValue("print/estimate_layout", "new")
    modern_manager = PrintManager(_DbStub(), print_font=QFont("Arial", 8))
    modern_payload = modern_manager.build_estimate_preview_payload(
        "V-004",
        estimate_data=estimate_data,
    )

    assert classic_payload is not None
    assert modern_payload is not None
    assert classic_manager.estimate_format == "classic"
    assert modern_manager.estimate_format == "modern"
    assert classic_payload.format_key == "classic"
    assert modern_payload.format_key == "modern"


def test_preview_print_font_change_updates_manager_and_persists(
    qt_app,
    settings_stub,
):
    del qt_app, settings_stub
    active_font = QFont("Arial", 8)
    active_font.float_size = 8.0
    manager = PrintManager(_DbStub(), print_font=active_font)
    selected_font = QFont("Arial", 12)
    selected_font.setBold(True)
    selected_font.float_size = 12.5

    manager._set_print_font(selected_font)

    settings = get_app_settings()
    assert manager.print_font is active_font
    assert active_font.float_size == 12.5
    assert active_font.bold()
    assert settings.value("font/family") == "Arial"
    assert settings.value("font/size_float") == 12.5
    assert settings.value("font/bold") is True


def test_classic_estimate_painter_writes_previous_modern_style_without_html(
    qt_app,
    settings_stub,
    tmp_path,
):
    del qt_app, settings_stub
    get_app_settings().setValue("print/estimate_layout", "classic")
    font = QFont("Courier New", 7)
    font.float_size = 7.0
    manager = PrintManager(_DbStub(), print_font=font)
    output_path = tmp_path / "classic-estimate-direct.pdf"

    _render_estimate_pdf(manager, multi_section_print_estimate(), output_path)
    pages, document = _pdf_pages(output_path)
    rendered = "\n".join(pages)

    assert document.pageCount() >= 1
    assert "ESTIMATE SLIP ONLY" in rendered
    assert "Gross" in rendered
    assert "Net" in rendered
    assert "S.Per%" not in rendered
    assert "%" in rendered
    assert "Silver Bars" in rendered
    assert "Quantity" not in rendered
    assert "Gross (g)" not in rendered
    assert "/Doz." not in rendered
    assert "GOODS NOT RETURNABLE" not in rendered


def test_direct_estimate_painter_writes_pdf(qt_app, settings_stub, tmp_path):
    del qt_app, settings_stub
    font = QFont("Courier New", 7)
    font.float_size = 7.0
    manager = PrintManager(_DbStub(), print_font=font)
    payload = manager.build_estimate_preview_payload(
        "EST-PARITY-001",
        estimate_data=multi_section_print_estimate(),
    )
    assert payload is not None
    assert isinstance(payload.document, EstimatePrintDocument)

    output_path = tmp_path / "modern-estimate-direct.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPageLayout(manager.printer.pageLayout())
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output_path))

    manager._render_document(printer, payload.document)

    assert output_path.read_bytes().startswith(b"%PDF-")
    assert output_path.stat().st_size > 1_000


def test_direct_estimate_painter_repeats_headers_and_keeps_summary_with_rows(
    qt_app,
    settings_stub,
    tmp_path,
):
    del qt_app, settings_stub
    font = QFont("Arial", 8)
    font.float_size = 8.0
    manager = PrintManager(_DbStub(), print_font=font)
    estimate_data = _long_estimate_data()
    output_path = tmp_path / "modern-estimate-multipage.pdf"
    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Landscape,
        QMarginsF(10, 10, 10, 10),
        QPageLayout.Unit.Millimeter,
    )

    _render_estimate_pdf(
        manager,
        estimate_data,
        output_path,
        page_layout=page_layout,
    )
    pages, document = _pdf_pages(output_path)

    assert document.pageCount() >= 2
    assert document.pagePointSize(0).width() > document.pagePointSize(0).height()
    assert all("Voucher: EST-PARITY-001" in page for page in pages)
    assert all("GOODS NOT RETURNABLE" not in page for page in pages)
    assert all("Page " not in page for page in pages)
    assert any("REGULAR GOODS (continued)" in page for page in pages[1:])
    assert "Long Regular Item 060" in pages[-1]
    assert "TOTAL" in pages[-1]
    assert "FINAL SILVER & AMOUNT" in pages[-1]


def test_direct_estimate_painter_elides_long_names_without_clipping(
    qt_app,
    settings_stub,
    tmp_path,
):
    del qt_app, settings_stub
    font = QFont("Arial", 8)
    font.float_size = 8.0
    manager = PrintManager(_DbStub(), print_font=font)
    estimate_data = multi_section_print_estimate()
    long_name = "Very long item name " + "with extra detail " * 20
    estimate_data["items"][0]["item_name"] = long_name
    output_path = tmp_path / "modern-estimate-long-name.pdf"

    _render_estimate_pdf(manager, estimate_data, output_path)
    pages, _document = _pdf_pages(output_path)
    rendered = "\n".join(pages)

    assert long_name not in rendered
    assert "Very long item name" in rendered
    assert "TOTAL" in rendered


def test_direct_estimate_painter_handles_portrait_and_large_font(
    qt_app,
    settings_stub,
    tmp_path,
):
    del qt_app, settings_stub
    font = QFont("Arial", 11)
    font.float_size = 11.0
    manager = PrintManager(_DbStub(), print_font=font)
    output_path = tmp_path / "modern-estimate-portrait-large-font.pdf"
    page_layout = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Portrait,
        QMarginsF(10, 10, 10, 10),
        QPageLayout.Unit.Millimeter,
    )

    _render_estimate_pdf(
        manager,
        multi_section_print_estimate(),
        output_path,
        page_layout=page_layout,
    )
    pages, document = _pdf_pages(output_path)

    assert document.pageCount() >= 1
    assert document.pagePointSize(0).height() > document.pagePointSize(0).width()
    assert "ESTIMATE SLIP ONLY" in pages[0]
    assert "Gross (g)" not in pages[0]
    assert "Poly (g)" not in pages[0]
    assert "Net (g)" not in pages[0]
    assert "Fine (g)" not in pages[0]
    assert "Purity (%)" not in pages[0]
    assert "Gross Poly Net %" in pages[0]
    assert "Fine Lbr" in pages[0]
    assert "Date:" not in pages[0]
    assert "FINAL SILVER & AMOUNT" in pages[-1]


def test_direct_estimate_painter_handles_custom_page_size(
    qt_app,
    settings_stub,
    tmp_path,
):
    del qt_app, settings_stub
    font = QFont("Arial", 7)
    font.float_size = 7.0
    manager = PrintManager(_DbStub(), print_font=font)
    output_path = tmp_path / "modern-estimate-counter-slip.pdf"
    page_size = QPageSize(
        QSizeF(120.0, 190.0),
        QPageSize.Unit.Millimeter,
        "Counter Slip",
    )
    page_layout = QPageLayout(
        page_size,
        QPageLayout.Orientation.Portrait,
        QMarginsF(6, 6, 6, 6),
        QPageLayout.Unit.Millimeter,
    )

    _render_estimate_pdf(
        manager,
        multi_section_print_estimate(),
        output_path,
        page_layout=page_layout,
    )
    pages, document = _pdf_pages(output_path)
    point_size = document.pagePointSize(0)

    assert document.pageCount() >= 1
    assert 335.0 < point_size.width() < 345.0
    assert 535.0 < point_size.height() < 545.0
    assert "Voucher: EST-PARITY-001" in pages[0]
    assert "FINAL SILVER & AMOUNT" in pages[-1]
