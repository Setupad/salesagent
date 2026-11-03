import asyncio
import logging
from datetime import UTC, datetime, time, timedelta
from typing import Any

from src.core.database.repositories.adapter_config import AdapterConfigRepository, read_adapter_config
from src.core.database.repositories.uow import ProductUoW
from src.core.exceptions import AdCPProductNotFoundError
from src.core.resolved_identity import PublicIdentity
from src.core.schemas.pricing import CpmPricingOption, VcpmPricingOption
from src.core.schemas.product import (
    GetProductsRequest,
    PackageDeliveryForecast,
    PackageForecastInput,
    Product,
    ProductRefinement,
    RefinementApplied,
)
from src.services.gam_product_forecast_service import (
    DEFAULT_FORECAST_TTL_HOURS,
    build_package_forecast_line_item,
    map_availability_forecast_to_adcp,
)

logger = logging.getLogger(__name__)


def _resolve_flight(package: PackageForecastInput, req: GetProductsRequest) -> PackageForecastInput:
    start, end = package.start_time, package.end_time
    if req.filters:
        if start is None and req.filters.start_date:
            start = datetime.combine(req.filters.start_date, time.min, tzinfo=UTC)
        if end is None and req.filters.end_date:
            end = datetime.combine(req.filters.end_date + timedelta(days=1), time.min, tzinfo=UTC)
    return package.model_copy(update={"start_time": start, "end_time": end})


def _forecast_package(
    product: Product, package: PackageForecastInput, identity: PublicIdentity
) -> PackageDeliveryForecast:
    if identity.principal is None:
        raise ValueError("Connect through an authorized buying agent for exact package forecasts.")
    pricing = next(
        (option.root for option in product.pricing_options if option.pricing_option_id == package.pricing_option_id),
        None,
    )
    if not isinstance(pricing, (CpmPricingOption, VcpmPricingOption)):
        raise ValueError("This provider supports exact forecasts for fixed CPM or vCPM pricing only.")
    config = read_adapter_config(identity.tenant_id)
    if config is None or config.adapter_type != "google_ad_manager" or not config.gam_network_code:
        raise ValueError("Exact package forecasting is not supported by this adapter.")
    from src.adapters.gam.client import GAMClientManager
    from src.adapters.gam.managers.targeting import GAMTargetingManager

    client = GAMClientManager(AdapterConfigRepository.get_gam_config(config), config.gam_network_code)
    targeting_manager = GAMTargetingManager(
        identity.tenant_id,
        gam_client=client.get_client() if package.targeting_overlay and package.targeting_overlay.custom else None,
        targeting_config=AdapterConfigRepository.get_gam_targeting_config(config),
        allow_value_creation=False,
    )
    with ProductUoW(identity.tenant_id) as uow:
        assert uow.products is not None
        stored_product = uow.products.get_by_id(product.product_id)
        if stored_product is None:
            raise AdCPProductNotFoundError()
        line_item = build_package_forecast_line_item(
            stored_product, package, pricing, targeting_manager=targeting_manager
        )
    result = client.get_service("ForecastService").getAvailabilityForecast(
        {"lineItem": line_item}, {"includeTargetingCriteriaBreakdown": False, "includeContendingLineItems": False}
    )
    generated_at = datetime.now(UTC)
    forecast = map_availability_forecast_to_adcp(
        result,
        currency=pricing.currency,
        product_id=product.product_id,
        generated_at=generated_at,
        valid_until=generated_at + timedelta(hours=DEFAULT_FORECAST_TTL_HOURS),
    )
    available = forecast["points"][0]["metrics"]["impressions"]["low"]
    forecast["points"][0]["metrics"]["impressions"] = {"mid": available}
    forecast["points"][0]["availability_status"] = (
        "available" if available >= line_item["primaryGoal"]["units"] else "unavailable"
    )
    assert package.start_time is not None and package.end_time is not None
    forecast["ext"]["forecast_period"] = {"start": package.start_time.isoformat(), "end": package.end_time.isoformat()}
    if pricing.pricing_model == "vcpm":
        forecast["ext"]["gam_unit_type"] = line_item["primaryGoal"]["unitType"]
    return PackageDeliveryForecast.model_validate(forecast)


async def refine_products(
    req: GetProductsRequest, products: list[Product], identity: PublicIdentity
) -> tuple[list[Product], list[RefinementApplied]]:
    catalog = {product.product_id: product for product in products}
    selected: dict[str, Product] = {}
    outcomes = []
    for wrapped in req.refine or []:
        entry = wrapped.root
        outcome: dict[str, Any] = {
            "scope": entry.scope,
            "status": "unable",
            "notes": "This refinement is not supported.",
        }
        if isinstance(entry, ProductRefinement):
            outcome["product_id"] = entry.product_id
            product = catalog.get(entry.product_id)
            if product is None:
                raise AdCPProductNotFoundError()
            if entry.action == "omit":
                outcome.update(status="applied", notes="Product omitted.")
            else:
                selected[product.product_id] = product
                if entry.package is not None:
                    outcome.update(await _refine_package(req, entry, product, identity))
                elif not entry.ask and entry.action in (None, "include"):
                    outcome.update(status="applied", notes="Product included.")
        elif entry.scope == "proposal":
            outcome["proposal_id"] = entry.proposal_id
        outcomes.append(RefinementApplied.model_validate(outcome))
    return list(selected.values()), outcomes


async def _refine_package(
    req: GetProductsRequest, entry: ProductRefinement, product: Product, identity: PublicIdentity
) -> dict[str, Any]:
    assert entry.package is not None
    product.forecast = None
    package = _resolve_flight(entry.package, req)
    try:
        if entry.ask:
            raise ValueError("Use structured package controls without a free-text ask for an exact forecast.")
        product.forecast = await asyncio.to_thread(_forecast_package, product, package, identity)
    except ValueError as exc:
        return {"notes": str(exc)}
    except Exception:
        logger.exception("Exact package forecast failed for product %s", product.product_id)
        return {"notes": "The forecasting service could not complete this exact package check."}
    return {
        "status": "applied",
        "notes": "Exact package availability checked; inventory is not reserved.",
        "result_product_id": product.product_id,
        "resolved_start_time": package.start_time,
        "resolved_end_time": package.end_time,
    }
