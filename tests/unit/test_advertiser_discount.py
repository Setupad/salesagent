from decimal import Decimal

import pytest

from src.core.helpers.pricing_helpers import discounted_rate, parse_discount_percentage


@pytest.mark.parametrize(
    ("rate", "percentage", "expected"),
    [
        ("10", "0", "10"),
        ("10", "15", "8.5"),
        ("10", "12.50", "8.75"),
        ("10", "99.99", "0.001"),
        ("0.001", "99.99", "0.0000001"),
    ],
)
def test_discounted_rate_preserves_precision(rate, percentage, expected):
    assert discounted_rate(Decimal(rate), Decimal(percentage)) == Decimal(expected)


@pytest.mark.parametrize("value", ["0", "15", "12.50", "99.99"])
def test_parse_discount_percentage(value):
    assert parse_discount_percentage(value) == Decimal(value)


@pytest.mark.parametrize("value", ["", "abc", "-1", "100", "100.01", "1.001", "NaN", "Infinity", "-Infinity"])
def test_parse_discount_percentage_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_discount_percentage(value)
