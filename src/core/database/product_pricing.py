"""Helper functions for reading product pricing from database.

Handles transition from legacy pricing fields to pricing_options table.
"""

import logging
from typing import Any

from src.core.database.models import Product as ProductModel

logger = logging.getLogger(__name__)


def get_product_pricing_options(product: ProductModel) -> list[dict[str, Any]]:
    """Get pricing options for a product.

    All products must have pricing_options - legacy fields are no longer supported.

    Args:
        product: Product ORM model (pricing_options relationship will be loaded if needed)

    Returns:
        List of pricing option dicts with keys:
        - pricing_model: str (e.g., "cpm")
        - rate: float | None
        - currency: str
        - is_fixed: bool
        - price_guidance: dict | None
        - parameters: dict | None
        - min_spend_per_package: float | None
    """
    pricing_options_list = []

    if product.pricing_options:
        for po in product.pricing_options:
            pricing_options_list.append(
                {
                    "pricing_option_id": po.pricing_option_id,
                    "pricing_model": po.pricing_model,
                    "rate": float(po.rate) if po.rate else None,
                    "currency": po.currency,
                    "is_fixed": po.is_fixed,
                    "price_guidance": po.price_guidance,
                    "parameters": po.parameters,
                    "min_spend_per_package": float(po.min_spend_per_package) if po.min_spend_per_package else None,
                }
            )
        return pricing_options_list

    # Product has no pricing options - this should not happen
    logger.error(f"Product {product.product_id} has no pricing_options - this is a data integrity error")
    return []


def get_primary_pricing_option(product: ProductModel) -> dict[str, Any] | None:
    """Get the primary (first) pricing option for a product.

    Returns None if product has no pricing.
    """
    options = get_product_pricing_options(product)
    return options[0] if options else None
