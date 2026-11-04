from datetime import UTC, datetime, timedelta

import pytest
from adcp.types import DeliveryForecast

from src.core.schemas import Targeting
from src.core.schemas.pricing import CpmPricingOption, VcpmPricingOption
from src.core.schemas.product import GetProductsRequest, PackageForecastInput
from src.services.gam_product_forecast_service import (
    build_package_forecast_line_item,
    fetch_product_availability_forecast,
    map_availability_forecast_to_adcp,
    refresh_cached_product_forecast,
)


def test_refine_package_is_announced_and_preserved() -> None:
    package = {
        "pricing_option_id": "cpm_fixed",
        "budget": 25000,
        "start_time": "2026-11-01T00:00:00Z",
        "end_time": "2026-11-30T23:59:59Z",
        "targeting_overlay": {"geo_countries": ["LT"]},
    }
    request = GetProductsRequest.model_validate(
        {"buying_mode": "refine", "refine": [{"scope": "product", "product_id": "prod_video", "package": package}]}
    )
    entry = request.refine[0]
    assert entry.package.budget == 25000
    assert [country.root for country in entry.package.targeting_overlay.geo_countries] == ["LT"]
    schema = GetProductsRequest.model_json_schema()
    assert any("package" in definition.get("properties", {}) for definition in schema["$defs"].values())


@pytest.mark.parametrize(
    ("pricing_class", "cost_type", "unit_type", "line_item_type", "priority"),
    [
        (CpmPricingOption, "CPM", "IMPRESSIONS", "PRICE_PRIORITY", 12),
        (VcpmPricingOption, "VCPM", "VIEWABLE_IMPRESSIONS", "STANDARD", 8),
    ],
)
def test_package_forecast_uses_exact_flight_and_budget_goal(
    pricing_class: type[CpmPricingOption] | type[VcpmPricingOption],
    cost_type: str,
    unit_type: str,
    line_item_type: str,
    priority: int,
) -> None:
    package = PackageForecastInput(
        pricing_option_id="fixed",
        budget=25000,
        start_time="2026-11-01T00:00:00Z",
        end_time="2026-11-30T23:59:59Z",
    )
    pricing = pricing_class(pricing_option_id="fixed", currency="USD", fixed_price=10)
    line_item = build_package_forecast_line_item(FakeProduct(), package, pricing)
    assert line_item["primaryGoal"] == {"goalType": "LIFETIME", "unitType": unit_type, "units": 2500000}
    assert line_item["costType"] == cost_type
    assert line_item["startDateTime"]["timeZoneId"] == "UTC"
    assert line_item["startDateTime"]["date"] == {"year": 2026, "month": 11, "day": 1}
    assert line_item["endDateTime"]["date"] == {"year": 2026, "month": 11, "day": 30}
    assert line_item["costPerUnit"] == {"currencyCode": "USD", "microAmount": 10000000}
    assert (line_item["lineItemType"], line_item["priority"]) == (line_item_type, priority)


def test_package_forecast_applies_country_targeting() -> None:
    class TargetingManager:
        geo_country_map = {"LT": "2440"}

        def build_targeting(self, overlay):
            assert overlay.geo_countries[0].root == "LT"
            return {"geoTargeting": {"targetedLocations": [{"id": "2440"}]}}

    package = PackageForecastInput(
        pricing_option_id="fixed",
        budget=100,
        start_time="2026-11-01T00:00:00Z",
        end_time="2026-11-30T23:59:59Z",
        targeting_overlay=Targeting(geo_countries=["LT"]),
    )
    pricing = CpmPricingOption(pricing_option_id="fixed", currency="USD", fixed_price=10)
    line_item = build_package_forecast_line_item(FakeProduct(), package, pricing, targeting_manager=TargetingManager())
    assert line_item["targeting"]["geoTargeting"] == {"targetedLocations": [{"id": "2440"}]}
    assert line_item["targeting"]["inventoryTargeting"]["targetedAdUnits"] == [
        {"adUnitId": "123", "includeDescendants": False}
    ]


def test_package_forecast_uses_buyer_selectable_custom_targeting() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from src.adapters.gam.managers.targeting import GAMTargetingManager

    class SelectableProduct(FakeProduct):
        targeting_template = {"selectable_key_value_pairs": {"CxSegments": {"values": ["female"]}}}

    client = Mock()
    client.GetService.return_value.getCustomTargetingValuesByStatement.return_value = SimpleNamespace(
        results=[SimpleNamespace(id=5678)]
    )
    manager = GAMTargetingManager(
        "test",
        gam_client=client,
        targeting_config={"custom_targeting_keys": {"CxSegments": "1234"}},
        allow_value_creation=False,
    )
    package = PackageForecastInput(
        pricing_option_id="fixed",
        budget=100,
        start_time="2026-11-10T00:00:00Z",
        end_time="2026-12-10T23:59:59Z",
        targeting_overlay=Targeting(custom={"gam": {"key_value_pairs": {"CxSegments": ["female"]}}}),
    )
    pricing = VcpmPricingOption(pricing_option_id="fixed", currency="EUR", fixed_price=10)
    line_item = build_package_forecast_line_item(SelectableProduct(), package, pricing, targeting_manager=manager)
    assert line_item["targeting"]["customTargeting"]["children"] == [
        {"xsi_type": "CustomCriteria", "keyId": 1234, "operator": "IS", "valueIds": [5678]}
    ]
    client.GetService.return_value.createCustomTargetingValues.assert_not_called()
    package.targeting_overlay = Targeting(
        custom={"gam": {"key_value_pairs": {"CxSegments": ["female"]}, "key_values": {"CxSegments": ["undeclared"]}}}
    )
    with pytest.raises(ValueError, match="GAM key/value"):
        build_package_forecast_line_item(SelectableProduct(), package, pricing, targeting_manager=manager)
    package.targeting_overlay = Targeting(custom={"gam": {"key_value_pairs": {"CxSegments": ["undeclared"]}}})
    with pytest.raises(ValueError, match="undeclared"):
        build_package_forecast_line_item(SelectableProduct(), package, pricing, targeting_manager=manager)


@pytest.mark.parametrize("found", [True, False])
def test_package_forecast_custom_value_lookup_never_creates(found: bool) -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from src.adapters.gam.managers.targeting import GAMTargetingManager
    from src.core.exceptions import AdCPAdapterError

    service = Mock()
    service.getCustomTargetingValuesByStatement.return_value = SimpleNamespace(
        results=[SimpleNamespace(id=5678)] if found else []
    )
    client = Mock()
    client.GetService.return_value = service
    manager = GAMTargetingManager(
        "test", gam_client=client, targeting_config={"custom_targeting_keys": {}}, allow_value_creation=False
    )
    if found:
        assert manager._get_or_create_custom_targeting_value("1234", "female") == 5678
    else:
        with pytest.raises(AdCPAdapterError):
            manager._get_or_create_custom_targeting_value("1234", "female")
    service.getCustomTargetingValuesByStatement.assert_called_once_with(
        {"query": "WHERE customTargetingKeyId = 1234 AND name = 'female'"}
    )
    service.createCustomTargetingValues.assert_not_called()


def test_package_forecast_loads_latvia_country_mapping() -> None:
    from src.adapters.gam.managers.targeting import GAMTargetingManager

    manager = GAMTargetingManager("test", targeting_config={"custom_targeting_keys": {}})
    package = PackageForecastInput(
        pricing_option_id="fixed",
        budget=100,
        start_time="2026-11-10T00:00:00Z",
        end_time="2026-12-10T23:59:59Z",
        targeting_overlay=Targeting(geo_countries=["LV"]),
    )
    pricing = VcpmPricingOption(pricing_option_id="fixed", currency="EUR", fixed_price=10)
    line_item = build_package_forecast_line_item(FakeProduct(), package, pricing, targeting_manager=manager)
    assert line_item["targeting"]["geoTargeting"] == {"targetedLocations": [{"id": "2428"}]}


class FakeForecastService:
    def __init__(self) -> None:
        self.line_item = None
        self.options = None

    def getAvailabilityForecast(self, line_item, options):
        self.line_item = line_item
        self.options = options
        return {"matchedUnits": 120_000, "availableUnits": 87_500, "possibleUnits": 130_000}


class FakeGAMClientManager:
    def __init__(self, service: FakeForecastService) -> None:
        self.service = service

    def get_service(self, service_name: str) -> FakeForecastService:
        assert service_name == "ForecastService"
        return self.service


class FakeProduct:
    product_id = "prod_video_1"
    name = "Video product"
    line_item_type = "STANDARD"
    priority = 10
    primary_goal_type = "DAILY"
    cost_type = "CPM"

    @property
    def effective_implementation_config(self) -> dict:
        return {
            "targeted_ad_unit_ids": ["123"],
            "targeted_placement_ids": ["456"],
            "include_descendants": False,
            "creative_placeholders": [{"width": 640, "height": 480, "expected_creative_count": 2}],
            "line_item_type": self.line_item_type,
            "priority": self.priority,
            "primary_goal_type": self.primary_goal_type,
            "cost_type": self.cost_type,
        }


class FakePricePriorityProduct(FakeProduct):
    line_item_type = "PRICE_PRIORITY"
    priority = 10
    primary_goal_type = "NONE"
    cost_type = "CPC"


class FakeProductRepository:
    def __init__(self, product: FakeProduct | None) -> None:
        self.product = product
        self.updated_product_id = None
        self.updated_fields = None

    def get_by_id(self, product_id: str):
        return self.product if product_id == "prod_video_1" else None

    def update_fields(self, product_id: str, **kwargs):
        self.updated_product_id = product_id
        self.updated_fields = kwargs
        return self.product


class FakeProductUoW:
    instance = None

    def __init__(self, tenant_id: str) -> None:
        self.tenant_id = tenant_id
        self.products = FakeProductRepository(FakeProduct())
        FakeProductUoW.instance = self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def test_maps_gam_availability_forecast_to_adcp_delivery_forecast() -> None:
    generated_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    valid_until = datetime.now(UTC) + timedelta(hours=6)
    gam_forecast = {
        "matchedUnits": 120_000,
        "availableUnits": 87_500,
        "possibleUnits": 130_000,
    }

    forecast = map_availability_forecast_to_adcp(
        gam_forecast,
        currency="USD",
        product_id="prod_video_1",
        generated_at=generated_at,
        valid_until=valid_until,
    )

    assert forecast["forecast_range_unit"] == "availability"
    assert forecast["method"] == "modeled"
    assert forecast["currency"] == "USD"
    assert forecast["generated_at"] == generated_at.isoformat().replace("+00:00", "Z")
    assert forecast["valid_until"] == valid_until.isoformat().replace("+00:00", "Z")
    assert forecast["ext"]["forecast_period"] == {
        "duration_days": 30,
        "start": "2026-01-01T12:00:00Z",
        "end": "2026-01-31T12:00:00Z",
    }
    assert forecast["points"] == [
        {
            "product_id": "prod_video_1",
            "metrics": {
                "impressions": {
                    "low": 87_500.0,
                    "mid": 120_000.0,
                    "high": 130_000.0,
                }
            },
        }
    ]

    DeliveryForecast.model_validate(forecast)


def test_fetch_product_availability_forecast_calls_gam_forecast_service() -> None:
    service = FakeForecastService()
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    forecast = fetch_product_availability_forecast(
        FakeGAMClientManager(service),
        FakeProduct(),
        currency="USD",
        now=now,
    )

    assert forecast["points"][0]["metrics"]["impressions"]["mid"] == 120_000.0
    assert service.options == {"includeTargetingCriteriaBreakdown": False, "includeContendingLineItems": False}
    assert service.line_item["lineItem"]["name"] == "30d Availability Forecast - Video product"
    assert service.line_item["lineItem"]["lineItemType"] == "STANDARD"
    assert service.line_item["lineItem"]["targeting"]["inventoryTargeting"] == {
        "targetedAdUnits": [{"adUnitId": "123", "includeDescendants": False}],
        "targetedPlacementIds": [456],
    }
    assert service.line_item["lineItem"]["creativePlaceholders"] == [
        {
            "size": {"width": 640, "height": 480, "isAspectRatio": False},
            "expectedCreativeCount": 2,
        }
    ]
    assert service.line_item["lineItem"]["costPerUnit"] == {"currencyCode": "USD", "microAmount": 0}
    assert service.line_item["lineItem"]["costType"] == "CPM"
    assert service.line_item["lineItem"]["priority"] == 8
    assert service.line_item["lineItem"]["primaryGoal"] == {
        "goalType": "LIFETIME",
        "unitType": "IMPRESSIONS",
        "units": 1,
    }
    assert service.line_item["lineItem"]["startDateTime"]["date"] == {"year": 2026, "month": 1, "day": 1}
    assert service.line_item["lineItem"]["endDateTime"]["date"] == {"year": 2026, "month": 1, "day": 31}
    DeliveryForecast.model_validate(forecast)


def test_cached_vcpm_forecast_counts_viewable_impressions() -> None:
    class VcpmProduct(FakeProduct):
        @property
        def effective_implementation_config(self):
            return {**super().effective_implementation_config, "cost_type": "VCPM"}

    service = FakeForecastService()
    forecast = fetch_product_availability_forecast(
        FakeGAMClientManager(service), VcpmProduct(), currency="EUR", now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    )
    assert service.line_item["lineItem"]["costType"] == "VCPM"
    assert service.line_item["lineItem"]["primaryGoal"]["unitType"] == "VIEWABLE_IMPRESSIONS"
    assert forecast["ext"]["gam_unit_type"] == "VIEWABLE_IMPRESSIONS"


def test_product_availability_forecast_uses_standard_line_item_for_price_priority_product() -> None:
    service = FakeForecastService()

    fetch_product_availability_forecast(
        FakeGAMClientManager(service),
        FakePricePriorityProduct(),
        currency="USD",
        now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    assert service.line_item["lineItem"]["lineItemType"] == "STANDARD"
    assert service.line_item["lineItem"]["priority"] == 8
    assert service.line_item["lineItem"]["costType"] == "CPM"
    assert service.line_item["lineItem"]["primaryGoal"] == {
        "goalType": "LIFETIME",
        "unitType": "IMPRESSIONS",
        "units": 1,
    }


def test_refresh_cached_product_forecast_persists_forecast_field() -> None:
    service = FakeForecastService()

    forecast = refresh_cached_product_forecast(
        FakeGAMClientManager(service),
        tenant_id="tenant_a",
        product_id="prod_video_1",
        currency="USD",
        uow_factory=FakeProductUoW,
        now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    uow = FakeProductUoW.instance
    assert uow is not None
    assert uow.tenant_id == "tenant_a"
    assert uow.products.updated_product_id == "prod_video_1"
    assert uow.products.updated_fields == {"forecast": forecast}
