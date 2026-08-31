from datetime import UTC, datetime, timedelta

from adcp.types import DeliveryForecast

from src.services.gam_product_forecast_service import (
    fetch_product_availability_forecast,
    map_availability_forecast_to_adcp,
    refresh_cached_product_forecast,
)


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

    @property
    def effective_implementation_config(self) -> dict:
        return {
            "targeted_ad_unit_ids": ["123"],
            "targeted_placement_ids": ["456"],
            "include_descendants": False,
            "creative_placeholders": [{"width": 640, "height": 480, "expected_creative_count": 2}],
            "line_item_type": "STANDARD",
            "priority": 6,
        }


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
        valid_until=valid_until,
    )

    assert forecast["forecast_range_unit"] == "availability"
    assert forecast["method"] == "modeled"
    assert forecast["currency"] == "USD"
    assert forecast["valid_until"] == valid_until.isoformat().replace("+00:00", "Z")
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
    assert service.line_item["targeting"]["inventoryTargeting"] == {
        "targetedAdUnits": [{"adUnitId": "123", "includeDescendants": False}],
        "targetedPlacements": [{"placementId": "456"}],
    }
    assert service.line_item["creativePlaceholders"] == [
        {
            "size": {"width": 640, "height": 480, "isAspectRatio": False},
            "expectedCreativeCount": 2,
        }
    ]
    assert service.line_item["costPerUnit"] == {"currencyCode": "USD", "microAmount": 0}
    assert service.line_item["startDateTime"]["date"] == {"year": 2026, "month": 1, "day": 1}
    assert service.line_item["endDateTime"]["date"] == {"year": 2026, "month": 1, "day": 31}
    DeliveryForecast.model_validate(forecast)


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
