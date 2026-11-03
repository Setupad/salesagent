"""Exercise the requested package-forecast extension through product discovery."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from pytest_bdd import given, parsers, then, when

from src.core.database.repositories.uow import MediaBuyUoW, ProductUoW
from src.core.schemas.product import PackageDeliveryForecast
from tests.bdd.steps._outcome_helpers import wire_field
from tests.bdd.steps.generic._dispatch import dispatch_request
from tests.factories import AdapterConfigFactory, PricingOptionFactory, PrincipalFactory, ProductFactory, TenantFactory
from tests.harness.product import ProductEnv


class PackageForecastEnv(ProductEnv):
    EXTERNAL_PATCHES = {
        **ProductEnv.EXTERNAL_PATCHES,
        "gam_client": "src.adapters.gam.client.GAMClientManager",
    }

    def seed_package_product(self, adapter: str) -> None:
        tenant = TenantFactory(tenant_id=self._tenant_id, ad_server=adapter)
        PrincipalFactory(tenant=tenant, principal_id=self._principal_id)
        AdapterConfigFactory(
            tenant=tenant,
            adapter_type="google_ad_manager" if adapter == "gam" else adapter,
            gam_network_code="123456" if adapter == "gam" else None,
            gam_refresh_token="test-refresh-token" if adapter == "gam" else None,
        )
        now = datetime.now(UTC)
        self.product = ProductFactory(
            tenant=tenant,
            targeting_template={},
            implementation_config={
                "targeted_ad_unit_ids": ["123"],
                "creative_placeholders": [{"width": 300, "height": 250}],
            },
            forecast={
                "forecast_range_unit": "availability",
                "method": "modeled",
                "currency": "USD",
                "generated_at": now.isoformat(),
                "valid_until": (now + timedelta(hours=6)).isoformat(),
                "points": [{"metrics": {"impressions": {"mid": 999999}}}],
            },
        )
        self.pricing = PricingOptionFactory(product=self.product, rate=Decimal("10.00"))
        self.base_state = deepcopy(
            (self.product.targeting_template, self.product.implementation_config, self.product.forecast)
        )
        self._commit_factory_data()

    def set_gam_availability(self, matched: int, available: int, possible: int) -> None:
        self.mock["gam_client"].return_value.get_service.return_value.getAvailabilityForecast.return_value = {
            "matchedUnits": matched,
            "availableUnits": available,
            "possibleUnits": possible,
        }

    def assert_exact_gam_request(self, start: str, end: str) -> None:
        manager = self.mock["gam_client"].return_value
        manager.get_service.assert_called_once_with("ForecastService")
        forecast_call = manager.get_service.return_value.getAvailabilityForecast
        line_item = forecast_call.call_args.args[0]["lineItem"]
        forecast_call.assert_called_once_with(
            {"lineItem": line_item},
            {"includeTargetingCriteriaBreakdown": False, "includeContendingLineItems": False},
        )
        assert line_item["primaryGoal"] == {"goalType": "LIFETIME", "unitType": "IMPRESSIONS", "units": 2500000}
        for field, timestamp in (("startDateTime", start), ("endDateTime", end)):
            boundary = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            assert line_item[field] == {
                "date": {"year": boundary.year, "month": boundary.month, "day": boundary.day},
                "hour": boundary.hour,
                "minute": boundary.minute,
                "second": boundary.second,
                "timeZoneId": "UTC",
            }
        assert line_item["costPerUnit"] == {"currencyCode": "USD", "microAmount": 10000000}
        assert line_item["targeting"]["inventoryTargeting"]["targetedAdUnits"] == [
            {"adUnitId": "123", "includeDescendants": True}
        ]

    def assert_read_only(self) -> None:
        with ProductUoW(self._tenant_id) as uow:
            products = uow.products.list_all()
            assert [product.product_id for product in products] == [self.product.product_id]
            product = products[0]
            assert (product.targeting_template, product.implementation_config, product.forecast) == self.base_state
            pricing = uow.products.get_by_id_with_pricing(self.product.product_id).pricing_options
            assert [(option.pricing_option_id, option.rate) for option in pricing] == [
                (self.pricing.pricing_option_id, Decimal("10.00"))
            ]
        with MediaBuyUoW(self._tenant_id) as uow:
            assert uow.media_buys.list_all() == []


@given(parsers.parse('a package forecast product on the "{adapter}" adapter with a cached forecast'))
def package_product(ctx: dict, adapter: str) -> None:
    ctx["env"].seed_package_product(adapter)


@given(parsers.parse("GAM reports {matched:d} matched, {available:d} available, and {possible:d} possible impressions"))
def gam_availability(ctx: dict, matched: int, available: int, possible: int) -> None:
    ctx["env"].set_gam_availability(matched, available, possible)


@when(parsers.parse('the buyer refines the product at CPM 10 USD with budget {budget:d} from "{start}" to "{end}"'))
def refine_package(ctx: dict, budget: int, start: str, end: str) -> None:
    env = ctx["env"]
    ctx["package_flight"] = (start, end)
    dispatch_request(
        ctx,
        buying_mode="refine",
        refine=[
            {
                "scope": "product",
                "product_id": env.product.product_id,
                "package": {
                    "pricing_option_id": env.pricing.pricing_option_id,
                    "budget": budget,
                    "start_time": start,
                    "end_time": end,
                },
            }
        ],
    )


@then("the package refinement is position-matched and applied to the same product with the exact flight")
def applied_package(ctx: dict) -> None:
    product_id = ctx["env"].product.product_id
    outcomes = wire_field(ctx, "refinement_applied")
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert (outcome["scope"], outcome["product_id"], outcome["status"]) == ("product", product_id, "applied"), outcome
    assert outcome["result_product_id"] == product_id
    for field, timestamp in zip(("resolved_start_time", "resolved_end_time"), ctx["package_flight"], strict=True):
        assert datetime.fromisoformat(outcome[field].replace("Z", "+00:00")) == datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    products = wire_field(ctx, "products")
    assert [product["product_id"] for product in products] == [product_id]
    pricing = products[0]["pricing_options"]
    assert len(pricing) == 1
    assert (pricing[0]["pricing_option_id"], pricing[0]["currency"], pricing[0]["fixed_price"]) == (
        ctx["env"].pricing.pricing_option_id,
        "USD",
        10,
    )


@then("the package availability forecast reports 87500 impressions as unavailable without a point budget")
def package_availability(ctx: dict) -> None:
    forecast = wire_field(ctx, "products")[0]["forecast"]
    PackageDeliveryForecast.model_validate(forecast)
    assert forecast["forecast_range_unit"] == "availability"
    assert forecast["currency"] == "USD"
    assert len(forecast["points"]) == 1
    point = forecast["points"][0]
    assert point["metrics"]["impressions"]["mid"] == 87500
    assert point["availability_status"] == "unavailable"
    assert "budget" not in point
    period = forecast["ext"]["forecast_period"]
    for field, timestamp in zip(("start", "end"), ctx["package_flight"], strict=True):
        assert datetime.fromisoformat(period[field].replace("Z", "+00:00")) == datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )


@then("GAM receives the exact UTC flight and a lifetime goal of 2500000 impressions")
def exact_gam_request(ctx: dict) -> None:
    ctx["env"].assert_exact_gam_request(*ctx["package_flight"])


@then("the package refinement is position-matched and unable with non-empty notes and no product forecast")
def unable_package(ctx: dict) -> None:
    outcomes = wire_field(ctx, "refinement_applied")
    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert (outcome["scope"], outcome["product_id"], outcome["status"]) == (
        "product",
        ctx["env"].product.product_id,
        "unable",
    )
    assert outcome["notes"] == "Exact package forecasting is not supported by this adapter."
    products = wire_field(ctx, "products")
    assert [product["product_id"] for product in products] == [ctx["env"].product.product_id]
    assert "forecast" not in products[0]


@then(
    parsers.parse(
        'the package check serves version "{version}" without changing the base product or creating a media buy'
    )
)
def read_only_package_check(ctx: dict, version: str) -> None:
    assert wire_field(ctx, "adcp_version") == version
    ctx["env"].assert_read_only()
