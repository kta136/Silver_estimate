"""Preview payload construction helpers extracted from PrintManager."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable

from .estimate_print_document import EstimatePrintDocument
from .print_format_spec import (
    DEFAULT_ESTIMATE_FORMAT,
    ESTIMATE_FORMAT_SPECS,
    normalize_estimate_format,
)


def _sanitize_filename_stem(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    normalized = normalized.strip("-.")
    return normalized or "document"


@dataclass(frozen=True)
class HtmlPrintDocument:
    """Legacy HTML document retained for silver-bar reports."""

    html_content: str
    table_mode: bool = True


PrintDocument = EstimatePrintDocument | HtmlPrintDocument


@dataclass(frozen=True)
class PrintPreviewPayload:
    """Immutable document and metadata consumed by preview and output paths."""

    document: PrintDocument
    title: str
    document_kind: str = "document"
    identifier: str = ""
    suggested_filename: str = "document.pdf"
    format_key: str = ""
    available_formats: tuple[str, ...] = ()
    format_factory: Callable[[str], PrintPreviewPayload | None] | None = None
    show_tunch: bool = False
    tunch_visibility_factory: Callable[[bool], PrintPreviewPayload | None] | None = None


class PrintPayloadBuilder:
    """Build preview payloads without owning preview or output behavior."""

    def build_estimate_preview_payload(
        self,
        voucher_no,
        *,
        fetch_estimate: Callable[[object], object],
        format_key: str = DEFAULT_ESTIMATE_FORMAT,
        estimate_data=None,
        show_tunch: bool = False,
    ) -> PrintPreviewPayload | None:
        resolved_data = (
            estimate_data if estimate_data is not None else fetch_estimate(voucher_no)
        )
        if not resolved_data:
            return None

        base_document = EstimatePrintDocument.from_mapping(resolved_data)

        def build_payload(
            selected_format: str,
            tunch_visible: bool,
        ) -> PrintPreviewPayload:
            normalized_format = normalize_estimate_format(selected_format)
            return PrintPreviewPayload(
                document=replace(
                    base_document,
                    format_key=normalized_format,
                    show_tunch=bool(tunch_visible),
                ),
                title=f"Print Preview - Estimate {voucher_no}",
                document_kind="estimate",
                identifier=str(voucher_no or ""),
                suggested_filename=(
                    f"{_sanitize_filename_stem(f'Estimate-{voucher_no}')}.pdf"
                ),
                format_key=normalized_format,
                available_formats=tuple(ESTIMATE_FORMAT_SPECS),
                format_factory=lambda next_format: build_payload(
                    next_format,
                    tunch_visible,
                ),
                show_tunch=bool(tunch_visible),
                tunch_visibility_factory=lambda visible: build_payload(
                    normalized_format,
                    visible,
                ),
            )

        return build_payload(format_key, show_tunch)

    def build_silver_bar_inventory_preview_payload(
        self,
        *,
        status_filter=None,
        fetch_bars: Callable[[object], object],
        render_inventory: Callable[[object, object], str],
    ) -> PrintPreviewPayload | None:
        bars = fetch_bars(status_filter)
        if not bars:
            return None

        return PrintPreviewPayload(
            document=HtmlPrintDocument(
                render_inventory(bars, status_filter),
                table_mode=True,
            ),
            title="Print Preview - Silver Bar Inventory",
            document_kind="silver_bar_inventory",
            identifier=str(status_filter or "all"),
            suggested_filename="Silver-Bar-Inventory.pdf",
        )

    def build_silver_bar_list_preview_payload(
        self,
        list_info,
        bars_in_list,
        *,
        render_list_details: Callable[[object, object], str],
    ) -> PrintPreviewPayload | None:
        if not list_info:
            return None

        identifier = (
            list_info["list_identifier"]
            if "list_identifier" in list_info
            and list_info["list_identifier"] is not None
            else "N/A"
        )
        return PrintPreviewPayload(
            document=HtmlPrintDocument(
                render_list_details(list_info, bars_in_list),
                table_mode=True,
            ),
            title=f"Print Preview - List {identifier}",
            document_kind="silver_bar_list",
            identifier=str(identifier),
            suggested_filename=(
                f"{_sanitize_filename_stem(f'Silver-Bar-List-{identifier}')}.pdf"
            ),
        )


__all__ = [
    "HtmlPrintDocument",
    "PrintDocument",
    "PrintPayloadBuilder",
    "PrintPreviewPayload",
]
