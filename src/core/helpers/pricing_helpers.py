"""Pricing option helper utilities.

Handles the RootModel wrapper pattern used by adcp 2.14.0+ for discriminated unions,
and owns the ``pricing_info`` projection a package row stores.
"""

from decimal import Decimal, InvalidOperation
from typing import Any


def parse_discount_percentage(value: str) -> Decimal:
    try:
        percentage = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Discount must be a number between 0 and 99.99.") from exc
    if not percentage.is_finite() or not Decimal("0") <= percentage <= Decimal("99.99"):
        raise ValueError("Discount must be a number between 0 and 99.99.")
    if percentage != percentage.quantize(Decimal("0.01")):
        raise ValueError("Discount must have at most two decimal places.")
    return percentage


def discounted_rate(rate: Decimal, discount_percentage: Decimal) -> Decimal:
    return rate * (Decimal("1") - discount_percentage / Decimal("100"))


def pricing_info_for(
    pricing_option: Any, *, bid_price: float | None = None, discount_percentage: Decimal = Decimal("0")
) -> dict[str, Any]:
    """The ``pricing_info`` that ``MediaPackage.package_config`` stores for a package.

    NOT a spec shape: ``pricing_info`` appears in no pinned schema and is never received
    from a buyer — ``package_config`` is an internal JSON column. What makes the shape
    binding is its READERS: the GAM order manager and ``src/adapters/utils/pricing.py``
    take a package's rate from ``pricing_info["bid_price"]``, so a writer that omits a key
    silently sends every auction package down a ``.get()`` default.

    ``bid_price`` is not a property of the option — it is what THIS package bid — so it is
    supplied by the caller rather than projected. Everything else is the option's own
    terms, unwrapped for the RootModel members adcp 2.14.0+ uses.
    """
    option = getattr(pricing_option, "root", pricing_option)
    rate = Decimal(str(option.rate)) if option.rate is not None else None
    if option.is_fixed and rate is not None:
        rate = discounted_rate(rate, discount_percentage)
    return {
        "pricing_model": option.pricing_model,
        "rate": float(rate) if rate is not None else None,
        "currency": option.currency,
        "is_fixed": option.is_fixed,
        "bid_price": bid_price,
    }


def pricing_option_has_rate(pricing_option: Any) -> bool:
    """Check if a pricing option carries a fixed rate.

    V3 renamed the fixed rate to ``fixed_price`` (auction options have no rate;
    they carry ``floor_price`` / ``price_guidance``). The pre-V3 ``rate`` key is
    still honored as a fallback for ORM rows and stored legacy dicts, whose
    column keeps that name. Before this check knew about ``fixed_price`` it only
    matched ``rate``, so every V3-shaped option counted as rate-less — the
    anonymous-pricing heuristic in GetProductsResponse.__str__ misfired for
    authenticated buyers, hidden by test fixtures that leaked ``rate`` through
    the SDK members' ``extra="allow"``.

    Handles multiple formats:
    - Dict format (from JSON/serialization): checks fixed_price, then rate
    - Pydantic RootModel wrapper: checks the wrapped member's fixed_price
    - Direct attribute access (SQLAlchemy models): checks fixed_price, then rate

    Args:
        pricing_option: A pricing option in any supported format

    Returns:
        True if the pricing option has a non-None fixed rate value
    """
    # Dict format (JSON/serialization)
    if isinstance(pricing_option, dict):
        return pricing_option.get("fixed_price", pricing_option.get("rate")) is not None

    # Unwrap RootModel wrapper if present, then check the model/row attributes
    target = getattr(pricing_option, "root", pricing_option)
    if getattr(target, "fixed_price", None) is not None:
        return True
    return getattr(target, "rate", None) is not None
