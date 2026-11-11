from copy import deepcopy
from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.conftest import EnvRoute, _run_env_route
from tests.bdd.steps._outcome_helpers import wire_dict, wire_field
from tests.bdd.steps.generic._dispatch import dispatch_request
from tests.harness.media_buy_create import MediaBuyCreateEnv


@pytest.fixture(autouse=True)
def _harness_env(request, ctx):
    route = EnvRoute(
        tag="advertiser-discount-orders",
        env_builder=lambda config: MediaBuyCreateEnv(e2e_config=config),
    )
    yield from _run_env_route(request, ctx, route, ctx.get("e2e_config"))


@given("an order catalog with fixed rates 10 and 20 and a 15 percent buyer discount")
def given_order_catalog(ctx: dict) -> None:
    ctx["discount_order_request"] = ctx["env"].setup_discount_order(Decimal("15"))


@when(parsers.parse('the discount buyer submits order "{key}"'))
def when_submit_order(ctx: dict, key: str) -> None:
    request = deepcopy(ctx["discount_order_request"])
    request["idempotency_key"] = f"discount-order-{key}-00000000"
    dispatch_request(ctx, **request)


@when(parsers.parse("the order buyer discount changes to {discount} percent"))
def when_change_discount(ctx: dict, discount: str) -> None:
    ctx["env"].set_order_discount(Decimal(discount))


@then(parsers.parse("the order saves rates {first} and {second} with budgets 1000 and 500"))
def then_saved_terms(ctx: dict, first: str, second: str) -> None:
    packages = wire_field(ctx, "packages")
    assert len(packages) == 2
    saved = ctx["env"].saved_order_packages(wire_field(ctx, "media_buy_id"))
    assert set(saved) == {package["package_id"] for package in packages}
    for package, rate, budget in zip(
        packages,
        [Decimal(first), Decimal(second)],
        [Decimal("1000"), Decimal("500")],
        strict=True,
    ):
        config = saved[package["package_id"]]
        assert Decimal(str(config["pricing_info"]["rate"])) == rate
        assert config["budget"] == float(budget), config
        assert config["pricing_info"]["currency"] == "USD"
        assert config["pricing_info"]["is_fixed"] is True
        assert config["pricing_info"]["pricing_model"] == "cpm"


@then("the order adapter receives the saved rates and unchanged budgets")
def then_adapter_terms(ctx: dict) -> None:
    env = ctx["env"]
    saved = env.saved_order_packages(wire_field(ctx, "media_buy_id"))
    assert len(saved) == 2
    if not env.is_e2e:
        adapter_call = env.mock["adapter"].return_value.create_media_buy.call_args
        adapter_packages = adapter_call.args[1]
        pricing_info = adapter_call.args[4]
        assert {package.package_id for package in adapter_packages} == set(saved)
        for package in adapter_packages:
            config = saved[package.package_id]
            assert package.cpm == config["pricing_info"]["rate"]
            assert package.budget == config["budget"]
            assert pricing_info[package.package_id] == config["pricing_info"]


@then("the buyer remembers the order response and saved package terms")
def then_remember_order(ctx: dict) -> None:
    response = wire_dict(ctx)
    ctx["remembered_order"] = deepcopy(response)
    ctx["remembered_terms"] = ctx["env"].saved_order_packages(wire_field(ctx, "media_buy_id"))
    assert len(ctx["remembered_terms"]) == 2


@then("the previous order retains its saved package terms")
def then_previous_order_terms(ctx: dict) -> None:
    previous_id = ctx["remembered_order"]["media_buy_id"]
    assert wire_field(ctx, "media_buy_id") != previous_id
    assert ctx["env"].saved_order_packages(previous_id) == ctx["remembered_terms"]


@then("the replay returns the remembered response and saved package terms")
def then_replayed_order(ctx: dict) -> None:
    assert wire_dict(ctx) == ctx["remembered_order"] | {"replayed": True}
    assert ctx["env"].saved_order_packages(wire_field(ctx, "media_buy_id")) == ctx["remembered_terms"]


scenarios("features/advertiser_discount_orders.feature")
