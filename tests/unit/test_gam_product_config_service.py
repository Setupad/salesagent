from src.services.gam_product_config_service import GAMProductConfigService


def test_non_guaranteed_default_config_uses_price_priority_default_priority() -> None:
    config = GAMProductConfigService.generate_default_config("non_guaranteed")

    assert config["line_item_type"] == "PRICE_PRIORITY"
    assert config["priority"] == 12
