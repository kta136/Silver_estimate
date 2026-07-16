"""Tests for estimate print layout formatting."""

from __future__ import annotations

import html
import re

from silverestimate.ui.estimate_print_renderer import EstimatePrintRenderer


def test_classic_weight_header_values_and_total_are_right_aligned() -> None:
    renderer = EstimatePrintRenderer(currency_formatter=lambda value: str(value))
    rendered = renderer.generate_old_format(
        {
            "header": {
                "voucher_no": "V-1",
                "silver_rate": 0.0,
                "note": "",
            },
            "items": [
                {
                    "item_name": "Ring",
                    "gross": 12.345,
                    "poly": 0.0,
                    "fine": 11.0,
                    "wage": 0.0,
                    "purity": 91.6,
                    "pieces": 1,
                    "wage_rate": 0.0,
                }
            ],
        }
    )

    pre_match = re.search(r"<pre>(.*?)</pre>", rendered, re.S)
    assert pre_match is not None
    preformatted = html.unescape(pre_match.group(1))
    lines = preformatted.splitlines()
    header_line = next(line for line in lines if "Quantity" in line)
    item_line = next(line for line in lines if "12.345" in line)
    total_line = next(line for line in lines if "12" in line and "12.345" not in line)

    weight_right_edge = header_line.index("Quantity") + len("Quantity")
    assert item_line.index("12.345") + len("12.345") == weight_right_edge
    assert total_line.index("12") + len("12") == weight_right_edge
