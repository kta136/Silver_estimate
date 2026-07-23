"""Generate the controlled PDF set used by the Qt binding migration review."""

from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QMarginsF, QSettings, QSizeF
from PySide6.QtGui import QFont, QFontDatabase, QPageLayout, QPageSize
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.ui.print_manager import PrintManager
from silverestimate.ui.print_payload_builder import PrintPreviewPayload
from tests.factories import multi_section_print_estimate


class _EstimateDbStub:
    @staticmethod
    def get_estimate_by_voucher(_voucher_no: object) -> None:
        return None


class _InventoryDbStub:
    BARS = (
        {
            "bar_id": 101,
            "estimate_voucher_no": "SYN-001",
            "weight": 125.500,
            "purity": 99.90,
            "fine_weight": 125.500 * 0.999,
            "date_added": "2026-07-23",
            "status": "AVAILABLE",
        },
        {
            "bar_id": 102,
            "estimate_voucher_no": "SYN-002",
            "weight": 80.250,
            "purity": 98.50,
            "fine_weight": 80.250 * 0.985,
            "date_added": "2026-07-23",
            "status": "AVAILABLE",
        },
    )

    @classmethod
    def get_silver_bars(cls, status_filter: object):
        assert status_filter == "AVAILABLE"
        return cls.BARS


def _ensure_print_fonts() -> None:
    windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
    font_dir = windows_dir / "Fonts"
    families = set(QFontDatabase.families())
    font_files: tuple[str, ...] = ()
    if "Arial" not in families:
        font_files += ("arial.ttf", "arialbd.ttf")
    if "Courier New" not in families:
        font_files += ("cour.ttf", "courbd.ttf")
    for filename in font_files:
        font_path = font_dir / filename
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))


def _a4_layout(
    orientation: QPageLayout.Orientation,
    margins: QMarginsF | None = None,
) -> QPageLayout:
    if margins is None:
        margins = QMarginsF(10, 2, 10, 2)
    return QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        orientation,
        margins,
        QPageLayout.Unit.Millimeter,
    )


def _render_payload(
    manager: PrintManager,
    payload: PrintPreviewPayload,
    output_path: Path,
    page_layout: QPageLayout | None = None,
    *,
    use_manager_layout: bool = True,
) -> None:
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(output_path))
    if page_layout is not None:
        assert printer.setPageLayout(page_layout)
    elif use_manager_layout:
        assert printer.setPageLayout(manager.printer.pageLayout())
    manager._render_document(printer, payload.document)
    if not output_path.is_file() or output_path.stat().st_size < 1_000:
        raise RuntimeError(f"PDF generation failed: {output_path}")


def _estimate_payload(
    manager: PrintManager,
    estimate_data: dict[str, object],
) -> PrintPreviewPayload:
    payload = manager.build_estimate_preview_payload(
        estimate_data["header"]["voucher_no"],
        estimate_data=estimate_data,
    )
    if payload is None:
        raise RuntimeError("Estimate payload generation returned no document")
    return payload


def _long_estimate_data(item_count: int = 60) -> dict[str, object]:
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


def _configure_controlled_settings(output_dir: Path) -> None:
    settings_dir = output_dir / ".settings"
    settings_dir.mkdir(exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(settings_dir),
    )
    settings = get_app_settings()
    settings.clear()
    settings.setValue("print/orientation", "Landscape")
    settings.setValue("print/page_size", "A4")
    settings.setValue("print/page_size_name", "A4")
    settings.setValue("print/margins", "10,2,10,2")
    settings.setValue("print/estimate_layout", "modern")
    settings.setValue("print/show_tunch", False)
    settings.sync()


def _reference_layouts() -> tuple[QPageLayout, QPageLayout, QPageLayout]:
    _ensure_print_fonts()
    uniform_landscape = _a4_layout(
        QPageLayout.Orientation.Landscape,
        QMarginsF(10, 10, 10, 10),
    )
    uniform_portrait = _a4_layout(
        QPageLayout.Orientation.Portrait,
        QMarginsF(10, 10, 10, 10),
    )
    reference_portrait = QPageLayout(
        QPageSize(QPageSize.PageSizeId.A4),
        QPageLayout.Orientation.Portrait,
        QMarginsF(12, 12, 12, 12),
        QPageLayout.Unit.Point,
    )
    return uniform_landscape, uniform_portrait, reference_portrait


def _generate_estimate_pdfs(
    output_dir: Path,
    uniform_landscape: QPageLayout,
    uniform_portrait: QPageLayout,
    reference_portrait: QPageLayout,
) -> list[Path]:
    generated: list[Path] = []

    classic_manager = PrintManager(_EstimateDbStub(), QFont("Courier New", 7))
    classic_manager.estimate_format = "classic"
    classic = output_dir / "classic-estimate-direct.pdf"
    _render_payload(
        classic_manager,
        _estimate_payload(classic_manager, multi_section_print_estimate()),
        classic,
    )
    generated.append(classic)

    direct_manager = PrintManager(_EstimateDbStub(), QFont("Courier New", 7))
    direct_manager.estimate_format = "modern"
    direct = output_dir / "modern-estimate-direct.pdf"
    _render_payload(
        direct_manager,
        _estimate_payload(direct_manager, multi_section_print_estimate()),
        direct,
    )
    generated.append(direct)

    modern_manager = PrintManager(_EstimateDbStub(), QFont("Arial", 8))
    modern_manager.estimate_format = "modern"
    long_data = multi_section_print_estimate()
    long_data["items"][0]["item_name"] = (
        "Very long item name " + "with extra detail " * 20
    )
    long_name = output_dir / "modern-estimate-long-name.pdf"
    _render_payload(
        modern_manager,
        _estimate_payload(modern_manager, long_data),
        long_name,
    )
    generated.append(long_name)

    multipage = output_dir / "modern-estimate-multipage.pdf"
    _render_payload(
        modern_manager,
        _estimate_payload(modern_manager, _long_estimate_data()),
        multipage,
        uniform_landscape,
    )
    generated.append(multipage)

    large_manager = PrintManager(_EstimateDbStub(), QFont("Arial", 11))
    large_manager.estimate_format = "modern"
    large_font = output_dir / "modern-estimate-portrait-large-font.pdf"
    _render_payload(
        large_manager,
        _estimate_payload(large_manager, multi_section_print_estimate()),
        large_font,
        uniform_portrait,
    )
    generated.append(large_font)

    tunch_manager = PrintManager(_EstimateDbStub(), QFont("Arial", 8))
    tunch_manager.estimate_format = "modern"
    tunch_manager.show_tunch = True
    tunch = output_dir / "modern-estimate-tunch-visible.pdf"
    _render_payload(
        tunch_manager,
        _estimate_payload(tunch_manager, multi_section_print_estimate()),
        tunch,
        reference_portrait,
    )
    generated.append(tunch)

    counter_manager = PrintManager(_EstimateDbStub(), QFont("Arial", 7))
    counter_manager.estimate_format = "modern"
    counter_layout = QPageLayout(
        QPageSize(
            QSizeF(120.0, 190.0),
            QPageSize.Unit.Millimeter,
            "Counter Slip",
        ),
        QPageLayout.Orientation.Portrait,
        QMarginsF(6, 6, 6, 6),
        QPageLayout.Unit.Millimeter,
    )
    counter = output_dir / "modern-estimate-counter-slip.pdf"
    _render_payload(
        counter_manager,
        _estimate_payload(counter_manager, multi_section_print_estimate()),
        counter,
        counter_layout,
    )
    generated.append(counter)
    return generated


def _generate_silver_bar_pdfs(
    output_dir: Path,
    reference_portrait: QPageLayout,
) -> list[Path]:
    generated: list[Path] = []
    inventory_manager = PrintManager(_InventoryDbStub(), QFont("Arial", 8))
    inventory_payload = inventory_manager.build_silver_bar_inventory_preview_payload(
        "AVAILABLE"
    )
    if inventory_payload is None:
        raise RuntimeError(
            "Silver-bar inventory payload generation returned no document"
        )
    inventory = output_dir / "silver-bar-inventory.pdf"
    _render_payload(
        inventory_manager,
        inventory_payload,
        inventory,
        reference_portrait,
    )
    generated.append(inventory)

    list_payload = inventory_manager.build_silver_bar_list_preview_payload(
        {
            "list_identifier": "SYN-LIST-001",
            "list_note": "Synthetic M0 reference baseline",
        },
        _InventoryDbStub.BARS,
    )
    if list_payload is None:
        raise RuntimeError("Silver-bar list payload generation returned no document")
    silver_list = output_dir / "silver-bar-list.pdf"
    _render_payload(
        inventory_manager,
        list_payload,
        silver_list,
        reference_portrait,
    )
    generated.append(silver_list)
    return generated


def generate_pdf_set(output_dir: Path) -> tuple[Path, ...]:
    output_dir.mkdir(parents=True, exist_ok=True)
    _configure_controlled_settings(output_dir)
    uniform_landscape, uniform_portrait, reference_portrait = _reference_layouts()
    generated = _generate_estimate_pdfs(
        output_dir,
        uniform_landscape,
        uniform_portrait,
        reference_portrait,
    )
    generated.extend(_generate_silver_bar_pdfs(output_dir, reference_portrait))

    return tuple(generated)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory that will receive the nine controlled PDF variants.",
    )
    args = parser.parse_args()

    app = QApplication.instance() or QApplication([])
    generated = generate_pdf_set(args.output_dir.resolve())
    app.processEvents()
    for path in generated:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
