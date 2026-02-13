import pytest

from silverestimate.services.item_import_parser import (
    ItemImportParseError,
    parse_adjustment_factor,
    parse_item_row,
)


def test_parse_adjustment_factor_accepts_multiply():
    op, value = parse_adjustment_factor("*1.25")
    assert op == "*"
    assert value == pytest.approx(1.25)


def test_parse_adjustment_factor_rejects_divide_by_zero():
    with pytest.raises(ItemImportParseError):
        parse_adjustment_factor("/0")


def test_parse_item_row_applies_q_conversion_then_adjustment():
    parsed = parse_item_row(
        ["X001", "Sample", "92.5", "Q", "1000"],
        code_column=0,
        name_column=1,
        purity_column=2,
        type_column=3,
        rate_column=4,
        adjustment_op="*",
        adjustment_val=1.1,
    )
    # 1000 Q-rate -> 1.0, then adjusted by *1.1
    assert parsed.wage_rate == pytest.approx(1.1)
    assert parsed.wage_type == "Q"
    assert parsed.code == "X001"


def test_parse_item_row_rejects_invalid_domain_values():
    with pytest.raises(ItemImportParseError):
        parse_item_row(
            ["X001", "Sample", "101.0", "WT", "10"],
            code_column=0,
            name_column=1,
            purity_column=2,
            type_column=3,
            rate_column=4,
        )
