"""Tests for typed Modern silver-bar print layouts."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from silverestimate.ui.silver_bar_print_document import (
    SilverBarInventoryPrintDocument,
    SilverBarListPrintDocument,
)
from silverestimate.ui.silver_bar_print_renderer import SilverBarPrintRenderer


def _bars() -> list[dict[str, object]]:
    return [
        {
            "bar_id": "<B-1>",
            "estimate_voucher_no": "V<script>",
            "weight": 12.5,
            "purity": 99.2,
            "fine_weight": 12.4,
            "date_added": "2026-07-20",
            "status": "In <Stock>",
        },
        {
            "weight": 7.25,
            "purity": 98,
            "fine_weight": 7.2,
        },
    ]


def _golden(name: str) -> str:
    return (
        (Path(__file__).parents[1] / "golden" / name)
        .read_text(encoding="utf-8")
        .rstrip("\n")
    )


def test_inventory_layout_matches_semantic_golden_and_keeps_text_literal() -> None:
    document = SilverBarInventoryPrintDocument.from_rows(
        _bars(),
        status_filter="<Available & Ready>",
        print_date="2026-07-26",
    )

    layout = SilverBarPrintRenderer().build_layout(document)

    assert layout.normalized_text() == _golden("modern_silver_bar_inventory.txt")
    assert "<script>" in layout.normalized_text()
    assert "&lt;" not in layout.normalized_text()
    assert tuple(column.key for column in layout.columns) == (
        "bar_id",
        "voucher",
        "weight",
        "purity",
        "fine",
        "date",
        "status",
    )


def test_list_layout_matches_semantic_golden_without_removed_fields() -> None:
    document = SilverBarListPrintDocument.from_rows(
        {
            "list_identifier": "LIST-<script>",
            "list_note": "<b>fragile</b>",
            "creation_date": "2026-07-01",
        },
        _bars(),
    )

    layout = SilverBarPrintRenderer().build_layout(document)
    rendered = layout.normalized_text()

    assert rendered == _golden("modern_silver_bar_list.txt")
    assert "Created:" not in rendered
    assert "Printed:" not in rendered
    assert "Bar ID" not in rendered
    assert "Status" not in rendered


def test_list_document_reads_sqlite_rows_and_formats_empty_report() -> None:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        list_info = connection.execute(
            "SELECT 'LIST-012' AS list_identifier, NULL AS list_note"
        ).fetchone()
        bar = connection.execute(
            "SELECT 12.5 AS weight, 99.2 AS purity, 12.4 AS fine_weight"
        ).fetchone()

        populated = SilverBarListPrintDocument.from_rows(list_info, [bar])
        empty = SilverBarListPrintDocument.from_rows(list_info, [])
    finally:
        connection.close()

    populated_text = SilverBarPrintRenderer().build_layout(populated).normalized_text()
    empty_text = SilverBarPrintRenderer().build_layout(empty).normalized_text()

    assert "12.500 | 99.20 | 12.400" in populated_text
    assert "TOTAL (1) | 12.500 |  | 12.400" in populated_text
    assert "Note: N/A" in empty_text
    assert "-- No bars assigned --" in empty_text
    assert "TOTAL (0) | 0.000 |  | 0.000" in empty_text


def test_inventory_document_groups_large_values_and_validates_numbers() -> None:
    document = SilverBarInventoryPrintDocument.from_rows(
        [
            {
                "weight": 123456.789,
                "purity": 99.9,
                "fine_weight": 123333.332,
            }
        ],
        print_date="26/07/2026",
    )
    rendered = SilverBarPrintRenderer().build_layout(document).normalized_text()

    assert "1,23,456.789" in rendered
    assert "1,23,333.332" in rendered

    with pytest.raises(ValueError, match=r"bars\[0\]\.weight must be numeric"):
        SilverBarInventoryPrintDocument.from_rows(
            [{"weight": "not-a-number"}],
        )


def test_silver_bar_renderer_exposes_direct_layout_and_painting_only() -> None:
    renderer = SilverBarPrintRenderer()

    assert callable(renderer.build_layout)
    assert callable(renderer.paint)
    assert not hasattr(renderer, "generate_inventory_html_table")
    assert not hasattr(renderer, "generate_list_details_html")
