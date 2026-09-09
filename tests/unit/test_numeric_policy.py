"""Business examples for decimal precision and halfway rounding."""

import pytest

from silverestimate.domain.numeric_policy import fixed_decimal, sum_values
from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_wage_amount,
)
from silverestimate.ui.estimate_table_formatting import format_indian_number


@pytest.mark.parametrize(
    "value,places,expected",
    [
        ("1.2345", 3, "1.235"),
        ("-1.2345", 3, "-1.235"),
        ("10.125", 2, "10.13"),
        ("-10.125", 2, "-10.13"),
        ("2.675", 2, "2.68"),
        ("-0.0001", 3, "0.000"),
        ("999.9995", 3, "1000.000"),
        ("2.5", 0, "3"),
    ],
)
def test_halfway_rounding_is_explicit_and_symmetric(value, places, expected):
    assert fixed_decimal(value, places) == expected


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_values_cannot_be_formatted_as_business_numbers(value):
    with pytest.raises(ValueError):
        fixed_decimal(value, 2)


def test_line_rounding_happens_before_aggregation():
    assert compute_net_weight(10.125, 0) == 10.13
    first = compute_fine_weight(10.125, 92.5)
    assert first == 9.37
    assert sum_values((first, first)) == 18.74
    assert compute_wage_amount("WT", net_weight=10.125, wage_rate=1, pieces=1) == 10.13
    assert compute_wage_amount("PC", net_weight=999, wage_rate=3.375, pieces=3) == 10.13
    assert format_indian_number(123456.785, 2) == "1,23,456.79"


def test_aggregation_does_not_quantize_historical_values():
    assert sum_values((1.23456, 2.34567)) == 3.58023
    assert sum_values((0.1, 0.2, -0.3)) == 0
