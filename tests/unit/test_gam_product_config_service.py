from src.services.gam_product_config_service import GAMProductConfigService


def test_default_config_preserves_declared_format_dimensions() -> None:
    formats = [
        {"id": "display_image", "width": 1200, "height": 300},
        {"id": "display_html", "width": 1200, "height": 300},
        {"id": "display_image", "width": 1200, "height": 400},
        {"id": "display_image", "width": 728, "height": 90},
        {"id": "display_js", "width": 1, "height": 1},
    ]
    config = GAMProductConfigService.generate_default_config("guaranteed", formats, pricing_model="vcpm")
    assert config["creative_placeholders"] == [
        {"width": width, "height": height, "expected_creative_count": 1, "is_native": False}
        for width, height in [(1200, 300), (1200, 400), (728, 90), (1, 1)]
    ]


def test_non_guaranteed_default_config_uses_price_priority_default_priority() -> None:
    config = GAMProductConfigService.generate_default_config("non_guaranteed")

    assert config["line_item_type"] == "PRICE_PRIORITY"
    assert config["priority"] == 12


def test_default_config_accepts_legacy_and_dimensionless_formats() -> None:
    config = GAMProductConfigService.generate_default_config(
        "guaranteed",
        ["display_728x90", {"format_id": "display_300x250"}, {"id": "video_standard"}, {"id": "native_standard"}],
    )
    assert config["creative_placeholders"] == [
        {"width": 728, "height": 90, "expected_creative_count": 1, "is_native": False},
        {"width": 300, "height": 250, "expected_creative_count": 1, "is_native": False},
        {"width": 640, "height": 480, "expected_creative_count": 1, "is_native": False},
        {"width": 1, "height": 1, "expected_creative_count": 1, "is_native": True},
    ]


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
