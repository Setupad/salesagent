import ast
from pathlib import Path

import pytest
from adcp.types import FrequencyCap

from src.adapters.gam.frequency import build_frequency_caps
from src.core.exceptions import AdCPValidationError
from src.core.schemas import FrequencyCap as LocalFrequencyCap


def test_local_frequency_defaults_to_package_application() -> None:
    cap = LocalFrequencyCap(suppress_minutes=60)
    assert cap.scope == "package"
    assert build_frequency_caps(None, cap) == [{"maxImpressions": 1, "numTimeUnits": 1, "timeUnit": "HOUR"}]


@pytest.mark.parametrize("for_forecast", [False, True])
def test_gam_rejects_local_media_buy_scope(for_forecast: bool) -> None:
    cap = LocalFrequencyCap(suppress_minutes=60, scope="media_buy")
    with pytest.raises(AdCPValidationError) as error:
        build_frequency_caps(None, cap, for_forecast=for_forecast)
    assert error.value.field == "targeting_overlay.frequency_cap.scope"


@pytest.mark.parametrize(
    ("minutes", "interval", "unit"),
    [(1, 1, "MINUTE"), (59, 59, "MINUTE"), (60, 1, "HOUR"), (90, 90, "MINUTE"), (1440, 1, "DAY"), (1500, 25, "HOUR")],
)
def test_suppression_preserves_exact_interval(minutes: int, interval: int, unit: str) -> None:
    cap = FrequencyCap(suppress_minutes=minutes)
    expected = [{"maxImpressions": 1, "numTimeUnits": interval, "timeUnit": unit}]
    assert build_frequency_caps(None, cap) == expected
    assert build_frequency_caps(None, cap, for_forecast=True) == expected


@pytest.mark.parametrize("entity", ["devices", "cookies"])
def test_count_and_cooldown_are_both_preserved(entity: str) -> None:
    cap = FrequencyCap(
        max_impressions=7,
        per=entity,
        window={"interval": 2, "unit": "days"},
        suppress={"interval": 120, "unit": "seconds"},
    )
    expected = [
        {"maxImpressions": 7, "numTimeUnits": 2, "timeUnit": "DAY"},
        {"maxImpressions": 1, "numTimeUnits": 2, "timeUnit": "MINUTE"},
    ]
    assert build_frequency_caps(None, cap) == expected
    assert build_frequency_caps(None, cap, for_forecast=True) == expected


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"suppress_minutes": 0.5}, "suppress_minutes"),
        ({"suppress_minutes": 60.5}, "suppress_minutes"),
        ({"suppress_minutes": float("inf")}, "suppress_minutes"),
        ({"suppress": {"interval": 61, "unit": "seconds"}}, "suppress"),
        ({"suppress": {"interval": 1, "unit": "campaign"}}, "suppress"),
        ({"suppress_minutes": 60, "scope": "media_buy"}, "scope"),
        ({"suppress_minutes": 60, "suppress": {"interval": 90, "unit": "minutes"}}, "suppress_minutes"),
        ({"max_impressions": 5}, "per"),
        ({"max_impressions": 5, "per": "devices"}, "window"),
        ({"suppress_minutes": 60, "window": {"interval": 1, "unit": "days"}}, "max_impressions"),
        ({}, ""),
    ],
)
def test_unrepresentable_frequency_is_rejected(payload: dict, field: str) -> None:
    with pytest.raises(AdCPValidationError) as error:
        build_frequency_caps(None, FrequencyCap(**payload), for_forecast=True)
    assert error.value.field == "targeting_overlay.frequency_cap" + (f".{field}" if field else "")


@pytest.mark.parametrize("entity", ["individuals", "households", "accounts", "custom"])
def test_unsupported_entity_is_rejected(entity: str) -> None:
    cap = FrequencyCap(max_impressions=5, per=entity, window={"interval": 1, "unit": "days"})
    with pytest.raises(AdCPValidationError) as error:
        build_frequency_caps(None, cap, for_forecast=True)
    assert error.value.field == "targeting_overlay.frequency_cap.per"


def test_campaign_count_is_available_only_for_creation() -> None:
    cap = FrequencyCap(max_impressions=5, per="devices", window={"interval": 1, "unit": "campaign"})
    assert build_frequency_caps(None, cap) == [{"maxImpressions": 5, "numTimeUnits": 1, "timeUnit": "LIFETIME"}]
    with pytest.raises(AdCPValidationError) as error:
        build_frequency_caps(None, cap, for_forecast=True)
    assert error.value.field == "targeting_overlay.frequency_cap.window"


def test_product_and_buyer_caps_merge_without_mutating_product() -> None:
    product_caps = [{"max_impressions": 8, "time_range": 24, "time_unit": "HOUR"}]
    cap = FrequencyCap(max_impressions=5, per="cookies", window={"interval": 1, "unit": "days"})
    assert build_frequency_caps(product_caps, cap, for_forecast=True) == [
        {"maxImpressions": 5, "numTimeUnits": 24, "timeUnit": "HOUR"}
    ]
    assert product_caps == [{"max_impressions": 8, "time_range": 24, "time_unit": "HOUR"}]


@pytest.mark.parametrize("for_forecast", [False, True], ids=["creation", "forecast"])
@pytest.mark.parametrize("reverse_order", [False, True], ids=["hours-first", "minutes-first"])
def test_equivalent_interval_merges_before_same_unit_conflict(reverse_order: bool, for_forecast: bool) -> None:
    product_caps = [
        {"max_impressions": 7, "time_range": 3, "time_unit": "HOUR"},
        {"max_impressions": 8, "time_range": 120, "time_unit": "MINUTE"},
    ]
    if reverse_order:
        product_caps.reverse()
    cap = FrequencyCap(max_impressions=3, per="devices", window={"interval": 2, "unit": "hours"})
    result = build_frequency_caps(product_caps, cap, for_forecast=for_forecast)
    assert sorted(result, key=lambda item: item["maxImpressions"]) == [
        {"maxImpressions": 3, "numTimeUnits": 120, "timeUnit": "MINUTE"},
        {"maxImpressions": 7, "numTimeUnits": 3, "timeUnit": "HOUR"},
    ]


@pytest.mark.parametrize("unit", ["MONTH", "LIFETIME", "POD", "STREAM", "UNKNOWN"])
def test_unforecastable_product_caps_are_rejected(unit: str) -> None:
    with pytest.raises(AdCPValidationError) as error:
        build_frequency_caps([{"max_impressions": 3, "time_range": 1, "time_unit": unit}], for_forecast=True)
    assert error.value.field == "frequency_caps[0].time_unit"


@pytest.mark.parametrize("unit", ["MONTH", "LIFETIME"])
def test_creation_preserves_product_caps(unit: str) -> None:
    assert build_frequency_caps([{"max_impressions": 3, "time_range": 1, "time_unit": unit}]) == [
        {"maxImpressions": 3, "numTimeUnits": 1, "timeUnit": unit}
    ]


def test_duplicate_unit_with_distinct_ranges_is_rejected() -> None:
    cap = FrequencyCap(
        suppress_minutes=30, max_impressions=5, per="devices", window={"interval": 90, "unit": "minutes"}
    )
    with pytest.raises(AdCPValidationError) as error:
        build_frequency_caps(None, cap, for_forecast=True)
    assert error.value.field == "targeting_overlay.frequency_cap"


def test_absent_or_zero_cooldown_needs_no_cap() -> None:
    assert build_frequency_caps(None) == []
    assert build_frequency_caps([], FrequencyCap(suppress_minutes=0)) == []


@pytest.mark.parametrize(
    ("product_cap", "field"),
    [
        ({"max_impressions": 0, "time_range": 1, "time_unit": "DAY"}, ".max_impressions"),
        ({"max_impressions": 5, "time_range": 0, "time_unit": "DAY"}, ".time_range"),
        ({"max_impressions": 5, "time_range": 1.5, "time_unit": "DAY"}, ".time_range"),
        ({"max_impressions": 5, "time_range": 1, "time_unit": "DAY", "scope": "campaign"}, ""),
    ],
)
def test_invalid_product_caps_are_rejected(product_cap: dict, field: str) -> None:
    with pytest.raises(AdCPValidationError) as error:
        build_frequency_caps([product_cap], for_forecast=True)
    assert error.value.field == f"frequency_caps[0]{field}"


@pytest.mark.parametrize(
    "owner", ["src/adapters/gam/managers/orders.py", "src/services/gam_product_forecast_service.py"]
)
def test_creation_and_forecasting_use_shared_frequency_converter(owner: str) -> None:
    root = Path(__file__).resolve().parents[2]
    tree = ast.parse((root / owner).read_text())
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "src.adapters.gam.frequency"
        and any(alias.name == "build_frequency_caps" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "build_frequency_caps"
        for node in ast.walk(tree)
    )
