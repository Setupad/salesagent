from decimal import Decimal

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import object_session

from src.core.database.product_pricing import get_product_pricing_options
from tests.factories import PricingOptionFactory, ProductFactory
from tests.harness._base import IntegrationEnv


@pytest.mark.requires_db
@pytest.mark.parametrize("preload", [False, True], ids=["lazy", "loaded"])
@pytest.mark.parametrize("is_fixed", [False, True], ids=["auction", "fixed"])
def test_product_pricing_loader_preserves_saved_options(integration_db, preload, is_fixed):
    with IntegrationEnv() as env:
        product = ProductFactory(tenant_id=env.tenant_id)
        pricing = PricingOptionFactory(
            product=product,
            currency="EUR",
            is_fixed=is_fixed,
            min_spend_per_package=Decimal("100.00"),
        )
        expected = {
            "pricing_option_id": pricing.pricing_option_id,
            "pricing_model": "cpm",
            "rate": 5.0 if is_fixed else None,
            "currency": "EUR",
            "is_fixed": is_fixed,
            "price_guidance": None if is_fixed else {"floor": 1.0},
            "parameters": None,
            "min_spend_per_package": 100.0,
        }
        session = object_session(product)
        assert session is not None
        session.expire(product, ["pricing_options"])
        if preload:
            assert len(product.pricing_options) == 1
        assert ("pricing_options" not in inspect(product).unloaded) == preload

        assert get_product_pricing_options(product) == [expected]
