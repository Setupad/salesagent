import pytest

from src.admin.blueprints.products import parse_pricing_options_from_form


def test_vcpm_form_saves_fixed_rate() -> None:
    options = parse_pricing_options_from_form({"pricing_model_0": "vcpm", "currency_0": "EUR", "rate_0": "10"})
    assert len(options) == 1
    assert options[0]["pricing_model"] == "vcpm"
    assert options[0]["is_fixed"] is True
    assert options[0]["rate"] == 10
    assert options[0]["price_guidance"] is None


def test_vcpm_form_requires_fixed_rate() -> None:
    with pytest.raises(ValueError, match="Rate is required for fixed pricing"):
        parse_pricing_options_from_form({"pricing_model_0": "vcpm", "currency_0": "EUR", "floor_0": "10"})
