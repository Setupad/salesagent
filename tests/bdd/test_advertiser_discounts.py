from decimal import Decimal

from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.steps._outcome_helpers import wire_field
from tests.bdd.steps.generic._dispatch import dispatch_request


@given(parsers.parse("a discount catalog with a {discount} percent buyer discount"))
def given_discount_catalog(ctx: dict, discount: str) -> None:
    product, default_buyer, discounted_buyer = ctx["env"].setup_advertiser_discount_catalog(Decimal(discount))
    ctx["discount_product_id"] = product.product_id
    ctx["discount_default_buyer"] = default_buyer.principal_id
    ctx["discount_original_buyer"] = discounted_buyer.principal_id


@when("the discount buyer discovers the catalog")
def when_discount_catalog(ctx: dict) -> None:
    dispatch_request(ctx, brief="display advertising")


@when(parsers.parse("the {buyer} discount catalog buyer discovers the catalog"))
def when_discount_catalog_buyer(ctx: dict, buyer: str) -> None:
    ctx["env"].switch_principal(ctx[f"discount_{buyer}_buyer"])
    dispatch_request(ctx, brief="display advertising")


def _catalog_option(ctx: dict, option_id: str) -> dict:
    products = wire_field(ctx, "products")
    matches = [product for product in products if product["product_id"] == ctx["discount_product_id"]]
    assert len(matches) == 1, products
    options = [option for option in matches[0]["pricing_options"] if option["pricing_option_id"] == option_id]
    assert len(options) == 1, matches[0]
    return options[0]


@then(parsers.parse("the discount catalog fixed price is {expected}"))
def then_discount_fixed_price(ctx: dict, expected: str) -> None:
    option = _catalog_option(ctx, "cpm_usd_fixed")
    assert Decimal(str(option["fixed_price"])) == Decimal(expected)
    assert option["currency"] == "USD"
    assert option["pricing_model"] == "cpm"


@then(parsers.parse("the discount catalog auction floor is {floor} and its median is {median}"))
def then_discount_auction_unchanged(ctx: dict, floor: str, median: str) -> None:
    option = _catalog_option(ctx, "cpm_usd_auction")
    assert Decimal(str(option["floor_price"])) == Decimal(floor)
    assert option["price_guidance"] == {"floor": float(floor), "p50": float(median)}
    assert "fixed_price" not in option


scenarios("features/advertiser_discounts.feature")
