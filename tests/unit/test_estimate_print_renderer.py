"""Tests for the direct Modern estimate print layout."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.estimate_print_layout import REGULAR_COLUMNS
from silverestimate.ui.estimate_print_renderer import (
    EstimatePrintRenderer,
    _section_gap_height,
)
from silverestimate.ui.modern_print_primitives import column_divider_positions
from tests.factories import multi_section_print_estimate


def test_modern_layout_matches_semantic_golden_for_all_sections() -> None:
    renderer = EstimatePrintRenderer()
    document = EstimatePrintDocument.from_mapping(multi_section_print_estimate())
    expected = (
        (Path(__file__).parents[1] / "golden" / "modern_estimate_multi_section.txt")
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )

    layout = renderer.build_modern_layout(document)

    assert layout.normalized_text() == expected
    assert "/Doz." not in layout.normalized_text()
    assert "Date:" in layout.normalized_text()
    assert tuple(section.title for section in layout.sections) == (
        "REGULAR GOODS",
        "RETURN GOODS",
        "SILVER BARS",
        "RETURN SILVER BARS",
    )
    assert all(
        0.0 <= column.start_ratio < column.start_ratio + column.width_ratio <= 1.0
        for section in layout.sections
        for column in section.columns
    )
    assert tuple(column.key for column in layout.sections[0].columns) == (
        "sno",
        "name",
        "gross",
        "poly",
        "net",
        "purity",
        "wage_rate",
        "pieces",
        "wage",
        "fine",
        "type",
    )
    regular_positions = {
        column.key: (column.start_ratio, column.width_ratio)
        for column in layout.sections[0].columns
    }
    for section in layout.sections[1:]:
        for column in section.columns:
            assert (column.start_ratio, column.width_ratio) == regular_positions[
                column.key
            ]
    assert "GOODS NOT RETURNABLE" not in layout.normalized_text()


def test_classic_layout_matches_previous_modern_fixed_width_structure() -> None:
    renderer = EstimatePrintRenderer()
    document = EstimatePrintDocument.from_mapping(
        multi_section_print_estimate(),
        format_key="classic",
    )
    expected = (
        (Path(__file__).parents[1] / "golden" / "classic_estimate_multi_section.txt")
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )

    layout = renderer.build_classic_layout(document)

    assert layout.normalized_text() == expected
    assert "Pcs/Doz." not in layout.normalized_text()
    assert "101.25" in layout.lines[1]
    assert "GOODS NOT RETURNABLE" not in layout.normalized_text()
    assert any("* * Silver Bars * *" in line for line in layout.lines)
    assert any("* * Return Goods * *" in line for line in layout.lines)


def test_tunch_column_is_optional_and_missing_values_stay_blank() -> None:
    renderer = EstimatePrintRenderer()
    estimate_data = deepcopy(multi_section_print_estimate())
    estimate_data["items"][0]["tunch"] = "92.5 + loss"

    modern_document = EstimatePrintDocument.from_mapping(
        estimate_data,
        show_tunch=True,
    )
    modern = renderer.build_modern_layout(modern_document)
    regular = modern.sections[0]

    assert tuple(column.key for column in regular.columns[:3]) == (
        "sno",
        "name",
        "tunch",
    )
    assert regular.rows[0].values[2] == "92.5 + loss"
    assert regular.rows[1].values[2] == ""
    assert regular.total_row.values[2] == ""

    classic_document = EstimatePrintDocument.from_mapping(
        estimate_data,
        format_key="classic",
        show_tunch=True,
    )
    classic = renderer.build_classic_layout(classic_document)
    header = next(line for line in classic.lines if "Item Name" in line)
    populated = next(line for line in classic.lines if "Chain Deluxe" in line)
    missing = next(line for line in classic.lines if "Anklet Pair" in line)

    assert "Item Name          Tunch" in header
    assert "92.5 +" in populated
    assert "92.5 +" not in missing


def test_zero_silver_rate_omits_cost_and_total_metrics() -> None:
    estimate_data = deepcopy(multi_section_print_estimate())
    estimate_data["header"]["silver_rate"] = 0

    layout = EstimatePrintRenderer().build_modern_layout(
        EstimatePrintDocument.from_mapping(estimate_data)
    )

    assert tuple(metric.label for metric in layout.final_metrics) == (
        "Total Lbr Amt (₹)",
        "Silver (g)",
    )
    assert "Silver Value (₹):" not in layout.normalized_text()
    assert "GRAND TOTAL (₹):" not in layout.normalized_text()


def test_modern_tables_share_aligned_columns_and_compact_section_gaps() -> None:
    renderer = EstimatePrintRenderer()
    layout = renderer.build_modern_layout(
        EstimatePrintDocument.from_mapping(multi_section_print_estimate())
    )
    style = type("Style", (), {"section_gap": 24.0})()
    divider_positions = column_divider_positions(REGULAR_COLUMNS, 100.0)

    assert len(divider_positions) == len(REGULAR_COLUMNS) - 1
    assert all(
        a < b for a, b in zip(divider_positions, divider_positions[1:], strict=False)
    )
    assert tuple(
        _section_gap_height(section, style) for section in layout.sections
    ) == (
        6.0,
        6.0,
        6.0,
        6.0,
    )


def test_zero_wages_remains_explicit_in_summary() -> None:
    estimate_data = deepcopy(multi_section_print_estimate())
    estimate_data["header"]["last_balance_amount"] = 0
    for item in estimate_data["items"]:
        item["wage"] = 0

    layout = EstimatePrintRenderer().build_modern_layout(
        EstimatePrintDocument.from_mapping(estimate_data)
    )

    assert tuple(metric.label for metric in layout.final_metrics) == (
        "Total Lbr Amt (₹)",
        "Silver Value (₹)",
        "GRAND TOTAL (₹)",
    )
    assert layout.final_metrics[0].value == "0.00"
