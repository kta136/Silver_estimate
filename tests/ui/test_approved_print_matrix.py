"""Exercise the shared Modern painter across the supported paper arrangements."""

from copy import deepcopy

import pytest
from PySide6.QtGui import QFont, QPageLayout
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPrintSupport import QPrinter

from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.estimate_print_renderer import EstimatePrintRenderer
from silverestimate.ui.print_page_settings import (
    PrintPageSettings,
    apply_print_page_settings_to_printer,
)
from tests.factories import multi_section_print_estimate
from tests.ui.test_print_manager import _ensure_print_test_font


@pytest.mark.parametrize(
    "paper", ["A4", "A5", "Letter", "Legal", "Thermal 80mm", "Custom"]
)
@pytest.mark.parametrize("orientation", ["Portrait", "Landscape"])
@pytest.mark.parametrize("rate", [0, 75000])
def test_modern_pdf_preserves_section_totals_and_final_summary(
    qt_app, tmp_path, paper, orientation, rate
):
    _ensure_print_test_font()
    sample = deepcopy(multi_section_print_estimate())
    sample["header"].update(silver_rate=rate, date="2026-09-06")
    regular = sample["items"][0]
    sample["items"] += [
        dict(
            regular, item_name="Silver chain with a long descriptive catalog name " * 4
        )
        for _ in range(120)
    ]
    for item in sample["items"]:
        item["tunch"] = "92.5 + loss"
        if rate == 0:
            item["wage"] = 0
    if rate == 0:
        sample["header"]["last_balance_amount"] = 0
    document = EstimatePrintDocument.from_mapping(sample, show_tunch=True)
    output = tmp_path / "matrix.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output))
    state = PrintPageSettings(
        page_size=paper,
        orientation=orientation,
        margins=(5, 5, 5, 5),
        page_width_mm=150 if paper == "Custom" else 0,
        page_height_mm=230 if paper == "Custom" else 0,
    )
    apply_print_page_settings_to_printer(printer, state, include_default_printer=False)
    layout = EstimatePrintRenderer().paint(
        printer, document, print_font=QFont("Arial", 8)
    )
    del printer
    pdf = QPdfDocument()
    try:
        assert pdf.load(str(output)) == QPdfDocument.Error.None_
        assert pdf.pageCount() > 1
        pages = [pdf.getAllText(page).text() for page in range(pdf.pageCount())]
        text = "\n".join(pages)
        assert text.count("SUBTOTAL") == 4
        assert all("Date: 2026-09-06" in page for page in pages)
        assert "Tunch" in text and "(continued)" in text
        assert "Last balance included:" in pages[-1]
        assert "Total Lbr Amt" in pages[-1]
        if rate:
            assert text.count("GRAND TOTAL") == 1
            assert "GRAND TOTAL" in pages[-1] and "Total Fine Weight" in pages[-1]
        else:
            assert "GRAND TOTAL" not in text and "Silver Value" not in text
            assert "Silver (g)" in pages[-1]
            assert layout.final_metrics[0].value == "0.00"
    finally:
        pdf.close()


def test_subtotal_cells_include_only_additive_columns():
    layout = EstimatePrintRenderer().build_modern_layout(
        EstimatePrintDocument.from_mapping(multi_section_print_estimate())
    )
    for section, pieces in zip(layout.sections, (6, 2, 2, 1), strict=True):
        values = dict(
            zip(
                (column.key for column in section.columns),
                section.total_row.values,
                strict=True,
            )
        )
        assert values["pieces"] == str(pieces)
        assert all(values[key] for key in ("gross", "poly", "net", "wage", "fine"))
        assert values["purity"] == values["wage_rate"] == ""


@pytest.mark.parametrize("format_key", ["modern", "classic"])
@pytest.mark.parametrize("show_tunch", [False, True])
def test_print_omits_item_codes_and_labels_lbr(
    qt_app, tmp_path, format_key, show_tunch
):
    _ensure_print_test_font()
    sample = deepcopy(multi_section_print_estimate())
    for index, item in enumerate(sample["items"]):
        item["item_code"] = f"PRIVATE-CODE-{index:03d}"
        item["tunch"] = "92.5"
    sample["items"][1]["item_name"] = ""
    document = EstimatePrintDocument.from_mapping(
        sample, format_key=format_key, show_tunch=show_tunch
    )
    output = tmp_path / "no-item-codes.pdf"
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output))
    apply_print_page_settings_to_printer(
        printer,
        PrintPageSettings(
            page_size="A4", orientation="Portrait" if show_tunch else "Landscape"
        ),
        include_default_printer=False,
    )
    printable_right = printer.pageLayout().paintRect(QPageLayout.Unit.Point).right()
    layout = EstimatePrintRenderer().paint(
        printer, document, print_font=QFont("Arial", 8)
    )
    del printer
    pdf = QPdfDocument()
    try:
        assert pdf.load(str(output)) == QPdfDocument.Error.None_
        assert all(
            pdf.getAllText(page).boundingRectangle().right() <= printable_right + 0.5
            for page in range(pdf.pageCount())
        )
        text = "\n".join(pdf.getAllText(page).text() for page in range(pdf.pageCount()))
        for rendered in (layout.normalized_text(), text):
            assert "PRIVATE-CODE" not in rendered
            assert "Code" not in rendered
            assert "Lbr" in rendered and "Lbr Amt" in rendered
            assert "Wage Rate" not in rendered and "W Rate" not in rendered
            assert ("Tunch" in rendered) is show_tunch
        assert document.items[0].item_code == "PRIVATE-CODE-000"
    finally:
        pdf.close()
