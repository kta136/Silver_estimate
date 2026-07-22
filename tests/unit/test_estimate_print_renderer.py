"""Tests for the direct Modern estimate print layout."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.estimate_print_layout import REGULAR_COLUMNS
from silverestimate.ui.estimate_print_renderer import (
    _SECTION_GAP_ROWS,
    EstimatePrintRenderer,
    _column_divider_positions,
)
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
    assert "Date:" not in layout.normalized_text()
    assert tuple(section.title for section in layout.sections) == (
        "REGULAR GOODS",
        "SILVER BARS",
        "RETURN GOODS",
        "RETURN SILVER BARS",
    )
    assert all(
        0.0 <= column.start_ratio < column.start_ratio + column.width_ratio <= 1.0
        for section in layout.sections
        for column in section.columns
    )
    assert tuple(column.key for column in layout.sections[1].columns) == (
        "sno",
        "name",
        "gross",
        "poly",
        "net",
        "purity",
        "fine",
        "wage",
    )
    regular_positions = {
        column.key: (column.start_ratio, column.width_ratio)
        for column in layout.sections[0].columns
    }
    assert regular_positions["gross"] == (0.29, 0.10)
    assert regular_positions["poly"] == (0.39, 0.09)
    assert regular_positions["net"] == (0.48, 0.10)
    assert regular_positions["wage"] == (0.92, 0.08)
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
    assert "GOODS NOT RETURNABLE" not in layout.normalized_text()
    assert any("* * Silver Bars * *" in line for line in layout.lines)
    assert any("* * Return Goods * *" in line for line in layout.lines)


def test_estimate_renderer_exposes_direct_layout_and_painting_only() -> None:
    renderer = EstimatePrintRenderer()

    assert callable(renderer.build_modern_layout)
    assert callable(renderer.build_classic_layout)
    assert callable(renderer.paint)
    assert not hasattr(renderer, "generate_modern_format")
    assert not hasattr(renderer, "_build_preformatted_html")


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

    assert tuple(column.key for column in regular.columns[:4]) == (
        "sno",
        "name",
        "tunch",
        "gross",
    )
    assert (regular.columns[1].start_ratio, regular.columns[1].width_ratio) == (
        0.04,
        0.18,
    )
    assert (regular.columns[2].start_ratio, regular.columns[2].width_ratio) == (
        0.22,
        0.07,
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
        "Fine Silver",
        "Labour",
    )
    assert "Silver Cost:" not in layout.normalized_text()
    assert "Total:" not in layout.normalized_text()


def test_modern_table_draws_pcs_fine_divider_and_uses_two_row_group_gaps() -> None:
    divider_positions = _column_divider_positions(REGULAR_COLUMNS, 100.0)

    assert 82.0 in divider_positions
    assert _SECTION_GAP_ROWS == 2.0
