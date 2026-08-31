from datetime import UTC, datetime, timedelta
from typing import Any

from adcp.types import DeliveryForecast

DEFAULT_FORECAST_DURATION_DAYS = 30
DEFAULT_FORECAST_TTL_HOURS = 6
DEFAULT_PRIORITY_BY_LINE_ITEM_TYPE = {
    "SPONSORSHIP": 4,
    "STANDARD": 8,
    "NETWORK": 12,
    "BULK": 12,
    "PRICE_PRIORITY": 12,
    "AD_EXCHANGE": 12,
    "HOUSE": 16,
    "CLICK_TRACKING": 16,
}


def fetch_product_availability_forecast(
    gam_client_manager: Any,
    product: Any,
    *,
    currency: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    requested_at = now or datetime.now(UTC)
    service = gam_client_manager.get_service("ForecastService")
    line_item = build_forecast_line_item(product, currency=currency, start_time=requested_at)
    options = {"includeTargetingCriteriaBreakdown": False, "includeContendingLineItems": False}
    gam_forecast = service.getAvailabilityForecast({"lineItem": line_item}, options)
    return map_availability_forecast_to_adcp(
        gam_forecast,
        currency=currency,
        product_id=product.product_id,
        valid_until=requested_at + timedelta(hours=DEFAULT_FORECAST_TTL_HOURS),
    )


def refresh_cached_product_forecast(
    gam_client_manager: Any,
    *,
    tenant_id: str,
    product_id: str,
    currency: str,
    now: datetime | None = None,
    uow_factory: Any | None = None,
) -> dict[str, Any]:
    if uow_factory is None:
        from src.core.database.repositories.uow import ProductUoW

        uow_factory = ProductUoW

    with uow_factory(tenant_id) as uow:
        products = uow.products
        if products is None:
            raise RuntimeError("Product repository was not initialized")
        product = products.get_by_id(product_id)
        if product is None:
            raise ValueError(f"Product {product_id!r} not found for tenant {tenant_id!r}")
        forecast = fetch_product_availability_forecast(gam_client_manager, product, currency=currency, now=now)
        products.update_fields(product_id, forecast=forecast)
        return forecast


def build_forecast_line_item(
    product: Any,
    *,
    currency: str,
    start_time: datetime,
    duration_days: int = DEFAULT_FORECAST_DURATION_DAYS,
) -> dict[str, Any]:
    config = product.effective_implementation_config
    end_time = start_time + timedelta(days=duration_days)
    targeting = _build_inventory_targeting(config)
    line_item_type = config.get("line_item_type", "STANDARD")
    return {
        "name": f"Forecast - {product.name}",
        "targeting": targeting,
        "creativePlaceholders": _build_creative_placeholders(config),
        "lineItemType": line_item_type,
        "priority": DEFAULT_PRIORITY_BY_LINE_ITEM_TYPE.get(line_item_type, 8),
        "costType": config.get("cost_type", "CPM"),
        "costPerUnit": {"currencyCode": currency, "microAmount": 0},
        "primaryGoal": {
            "goalType": "LIFETIME",
            "unitType": config.get("primary_goal_unit_type", "IMPRESSIONS"),
            "units": config.get("forecast_goal_units", 1),
        },
        "startDateTime": _to_gam_datetime(start_time, config.get("time_zone", "America/New_York")),
        "endDateTime": _to_gam_datetime(end_time, config.get("time_zone", "America/New_York")),
    }


def _build_inventory_targeting(config: dict[str, Any]) -> dict[str, Any]:
    inventory_targeting: dict[str, Any] = {}
    targeted_ad_unit_ids = config.get("targeted_ad_unit_ids") or []
    targeted_placement_ids = config.get("targeted_placement_ids") or []
    include_descendants = config.get("include_descendants", True)

    if targeted_ad_unit_ids:
        inventory_targeting["targetedAdUnits"] = [
            {"adUnitId": ad_unit_id, "includeDescendants": include_descendants} for ad_unit_id in targeted_ad_unit_ids
        ]
    if targeted_placement_ids:
        inventory_targeting["targetedPlacements"] = [
            {"placementId": placement_id} for placement_id in targeted_placement_ids
        ]
    return {"inventoryTargeting": inventory_targeting} if inventory_targeting else {}


def _build_creative_placeholders(config: dict[str, Any]) -> list[dict[str, Any]]:
    placeholders = config.get("creative_placeholders") or [{"width": 300, "height": 250, "expected_creative_count": 1}]
    return [
        {
            "size": {
                "width": int(placeholder["width"]),
                "height": int(placeholder["height"]),
                "isAspectRatio": bool(placeholder.get("is_aspect_ratio", False)),
            },
            "expectedCreativeCount": int(placeholder.get("expected_creative_count", 1)),
        }
        for placeholder in placeholders
    ]


def _to_gam_datetime(value: datetime, time_zone: str) -> dict[str, Any]:
    return {
        "date": {"year": value.year, "month": value.month, "day": value.day},
        "hour": value.hour,
        "minute": value.minute,
        "second": value.second,
        "timeZoneId": time_zone,
    }


def map_availability_forecast_to_adcp(
    gam_forecast: dict[str, Any],
    *,
    currency: str,
    product_id: str,
    valid_until: datetime,
) -> dict[str, Any]:
    forecast = {
        "forecast_range_unit": "availability",
        "method": "modeled",
        "currency": currency,
        "valid_until": valid_until.isoformat(),
        "points": [
            {
                "product_id": product_id,
                "metrics": {
                    "impressions": {
                        "low": float(_get_gam_value(gam_forecast, "availableUnits")),
                        "mid": float(_get_gam_value(gam_forecast, "matchedUnits")),
                        "high": float(_get_gam_value(gam_forecast, "possibleUnits")),
                    }
                },
            }
        ],
    }
    return DeliveryForecast.model_validate(forecast).model_dump(mode="json", exclude_none=True)


def _get_gam_value(gam_forecast: Any, field_name: str) -> Any:
    if isinstance(gam_forecast, dict):
        return gam_forecast[field_name]
    return getattr(gam_forecast, field_name)
