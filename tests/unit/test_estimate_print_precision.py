"""Estimate columns choose precision from all rows and subtotals."""

import pytest

from silverestimate.ui.estimate_print_document import EstimatePrintDocument
from silverestimate.ui.estimate_print_renderer import EstimatePrintRenderer
from tests.factories import regular_item

FIELDS = ("gross", "poly", "net_wt", "purity", "wage_rate", "pieces", "fine", "wage")


def _layout(items):
    document = EstimatePrintDocument.from_mapping(
        {"header": {"voucher_no": "precision", "silver_rate": 0}, "items": items},
    )
    return EstimatePrintRenderer().build_modern_layout(document)


def _column(layout, field, names=("First", "Second")):
    field = "net" if field == "net_wt" else field
    return [
        row.values[next(i for i, col in enumerate(section.columns) if col.key == field)]
        for section in layout.sections
        for row in section.rows
        if row.values[1] in names
    ]


@pytest.mark.parametrize("field", FIELDS)
@pytest.mark.parametrize(
    "values,expected",
    [
        ((10, 20), ["10", "20"]),
        ((10, 20.25), ["10.00", "20.25"]),
        ((0, 0), ["0", "0"]),
        ((-0.001, 9.999), ["0", "10"]),
        ((-1.005, 2), ["-1.01", "2.00"]),
    ],
)
def test_precision_is_shared_by_every_row_in_a_column(field, values, expected):
    items = [
        regular_item(item_name=name, **{field: value})
        for name, value in zip(("First", "Second"), values, strict=True)
    ]
    assert _column(_layout(items), field) == expected


def test_subtotal_fraction_keeps_decimals_even_when_rows_round_to_whole():
    layout = _layout(
        [
            regular_item(item_name="First", gross=10.004),
            regular_item(item_name="Second", gross=20.004),
        ],
    )
    assert _column(layout, "gross") == ["10.00", "20.00"]
    assert layout.sections[0].total_row.values[2] == "30.01"
    assert layout.sections[0].total_row.values[5:7] == ("", "")


def test_sections_choose_precision_independently():
    layout = _layout(
        [
            regular_item(item_name="First", gross=10),
            regular_item(item_name="Second", gross=20.25, is_return=True),
        ],
    )
    assert _column(layout, "gross") == ["10", "20.25"]
