from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.helpers.pricing_helpers import pricing_info_for


@pytest.mark.parametrize("discount, expected_rate", [("0", 10.0), ("15", 8.5)])
def test_fixed_pricing_info_applies_discount(discount: str, expected_rate: float) -> None:
    option = SimpleNamespace(pricing_model="cpm", rate=Decimal("10"), currency="USD", is_fixed=True)

    assert pricing_info_for(option, discount_percentage=Decimal(discount)) == {
        "pricing_model": "cpm",
        "rate": expected_rate,
        "currency": "USD",
        "is_fixed": True,
        "bid_price": None,
    }
    assert option.rate == Decimal("10")


def test_pricing_info_defaults_to_no_discount() -> None:
    option = SimpleNamespace(pricing_model="cpm", rate=Decimal("10"), currency="USD", is_fixed=True)

    assert pricing_info_for(option) == pricing_info_for(option, discount_percentage=Decimal("0"))


@pytest.mark.parametrize("rate", [None, Decimal("10")])
def test_auction_pricing_info_preserves_rate_and_bid(rate: Decimal | None) -> None:
    option = SimpleNamespace(pricing_model="cpm", rate=rate, currency="USD", is_fixed=False)

    assert pricing_info_for(option, bid_price=7.25, discount_percentage=Decimal("15")) == {
        "pricing_model": "cpm",
        "rate": float(rate) if rate is not None else None,
        "currency": "USD",
        "is_fixed": False,
        "bid_price": 7.25,
    }
