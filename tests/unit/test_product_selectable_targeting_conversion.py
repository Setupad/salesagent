from decimal import Decimal

from src.core.database.models import PricingOption
from src.core.product_conversion import convert_product_model_to_schema
from tests.helpers.adcp_factories import create_test_db_product


def test_conversion_exposes_selectable_key_value_pairs_in_ext():
    selectable = {"sport": {"display_name": "Sport", "values": ["basketball", "football"]}}
    product = create_test_db_product(
        tenant_id="selectable_targeting_test",
        targeting_template={"selectable_key_value_pairs": selectable},
    )
    product.pricing_options = [
        PricingOption.create(
            tenant_id=product.tenant_id,
            product_id=product.product_id,
            pricing_model="cpm",
            rate=Decimal("10.0"),
            currency="USD",
            is_fixed=True,
        )
    ]

    schema_product = convert_product_model_to_schema(product)

    assert schema_product.model_dump()["ext"]["prebid"]["selectable_key_value_pairs"] == selectable