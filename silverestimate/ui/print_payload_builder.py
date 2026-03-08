"""Preview payload construction helpers extracted from PrintManager."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


def _sanitize_filename_stem(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip())
    normalized = normalized.strip("-.")
    return normalized or "document"


@dataclass(frozen=True)
class PrintPreviewPayload:
    """Serialized preview payload that can be prepared before opening the dialog."""

    html_content: str
    title: str
    table_mode: bool = False
    document_kind: str = "document"
    identifier: str = ""
    suggested_filename: str = "document.pdf"
    layout_mode: str = ""
    available_layouts: tuple[str, ...] = ()
    layout_factory: Callable[[str], "PrintPreviewPayload | None"] | None = None


class PrintPayloadBuilder:
    """Build preview payloads without owning preview or rendering UI behavior."""

    def build_estimate_preview_payload(
        self,
        voucher_no,
        *,
        layout_mode,
        fetch_estimate: Callable[[object], object],
        render_old: Callable[[object], str],
        render_new: Callable[[object], str],
        render_thermal: Callable[[object], str],
        estimate_data=None,
    ) -> PrintPreviewPayload | None:
        resolved_data = (
            estimate_data if estimate_data is not None else fetch_estimate(voucher_no)
        )
        if not resolved_data:
            return None

        def build_payload(selected_layout: str) -> PrintPreviewPayload:
            normalized_layout = (selected_layout or "old").lower()
            if normalized_layout == "new":
                html_text = render_new(resolved_data)
            elif normalized_layout == "thermal":
                html_text = render_thermal(resolved_data)
            else:
                normalized_layout = "old"
                html_text = render_old(resolved_data)

            return PrintPreviewPayload(
                html_content=html_text,
                title=f"Print Preview - Estimate {voucher_no}",
                table_mode=False,
                document_kind="estimate",
                identifier=str(voucher_no or ""),
                suggested_filename=(
                    f"{_sanitize_filename_stem(f'Estimate-{voucher_no}')}.pdf"
                ),
                layout_mode=normalized_layout,
                available_layouts=("old", "new", "thermal"),
                layout_factory=build_payload,
            )

        return build_payload(layout_mode)

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
            html_content=render_inventory(bars, status_filter),
            title="Print Preview - Silver Bar Inventory",
            table_mode=True,
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
            if "list_identifier" in list_info.keys()
            and list_info["list_identifier"] is not None
            else "N/A"
        )
        return PrintPreviewPayload(
            html_content=render_list_details(list_info, bars_in_list),
            title=f"Print Preview - List {identifier}",
            table_mode=True,
            document_kind="silver_bar_list",
            identifier=str(identifier),
            suggested_filename=(
                f"{_sanitize_filename_stem(f'Silver-Bar-List-{identifier}')}.pdf"
            ),
        )
