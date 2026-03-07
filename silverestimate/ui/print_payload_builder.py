"""Preview payload construction helpers extracted from PrintManager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class PrintPreviewPayload:
    """Serialized preview payload that can be prepared before opening the dialog."""

    html_content: str
    title: str
    table_mode: bool = False


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

        normalized_layout = (layout_mode or "old").lower()
        if normalized_layout == "new":
            html_text = render_new(resolved_data)
        elif normalized_layout == "thermal":
            html_text = render_thermal(resolved_data)
        else:
            html_text = render_old(resolved_data)

        return PrintPreviewPayload(
            html_content=html_text,
            title=f"Print Preview - Estimate {voucher_no}",
            table_mode=False,
        )

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
        )
