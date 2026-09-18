from src.services.gam_product_config_service import GAMProductConfigService


def test_non_guaranteed_default_config_uses_price_priority_default_priority() -> None:
    config = GAMProductConfigService.generate_default_config("non_guaranteed")

    assert config["line_item_type"] == "PRICE_PRIORITY"
    assert config["priority"] == 12


def test_vcpm_default_config_uses_standard_line_item() -> None:
    config = GAMProductConfigService.generate_default_config("non_guaranteed", pricing_model="vcpm")

    assert config["line_item_type"] == "STANDARD"
    assert config["priority"] == 8
    assert config["primary_goal_type"] == "LIFETIME"
    assert config["delivery_rate_type"] == "EVENLY"


def test_vcpm_effective_line_item_type_overrides_stale_config() -> None:
    line_item_type = GAMProductConfigService.get_effective_line_item_type(
        {"line_item_type": "PRICE_PRIORITY"},
        [{"pricing_model": "vcpm", "is_fixed": False}],
    )

    assert line_item_type == "STANDARD"


def test_effective_line_item_type_uses_stored_config_for_non_vcpm() -> None:
    line_item_type = GAMProductConfigService.get_effective_line_item_type(
        {"line_item_type": "PRICE_PRIORITY"},
        [{"pricing_model": "cpm", "is_fixed": False}],
    )

    assert line_item_type == "PRICE_PRIORITY"
