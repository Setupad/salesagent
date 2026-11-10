from typing import Any

from adcp.types import Duration

from src.core.exceptions import AdCPValidationError
from src.core.schemas import FrequencyCap

_MINUTES_PER_UNIT = {"MINUTE": 1, "HOUR": 60, "DAY": 1440, "WEEK": 10080}
_CREATION_UNITS = {*_MINUTES_PER_UNIT, "MONTH", "LIFETIME", "POD", "STREAM"}


def build_frequency_caps(
    product_caps: list[dict[str, Any]] | None,
    buyer_cap: FrequencyCap | None = None,
    *,
    for_forecast: bool = False,
) -> list[dict[str, Any]]:
    caps: list[dict[str, Any]] = []
    for index, cap in enumerate(product_caps or []):
        field = f"frequency_caps[{index}]"
        if set(cap) - {"max_impressions", "time_range", "time_unit"}:
            raise AdCPValidationError(field=field)
        impressions, interval, unit = cap.get("max_impressions"), cap.get("time_range"), cap.get("time_unit")
        for value, name in ((impressions, "max_impressions"), (interval, "time_range")):
            if type(value) is not int or not 1 <= value <= 2_147_483_647:
                raise AdCPValidationError(field=f"{field}.{name}")
        if unit not in (_MINUTES_PER_UNIT if for_forecast else _CREATION_UNITS):
            raise AdCPValidationError(field=f"{field}.time_unit")
        caps.append({"maxImpressions": impressions, "numTimeUnits": interval, "timeUnit": unit})
    if buyer_cap is not None:
        caps.extend(_buyer_frequency_caps(buyer_cap, for_forecast=for_forecast))
    return _merge_frequency_caps(caps)


def _buyer_frequency_caps(cap: FrequencyCap, *, for_forecast: bool) -> list[dict[str, Any]]:
    field = "targeting_overlay.frequency_cap"
    if getattr(cap, "scope", "package") != "package":
        raise AdCPValidationError(field=f"{field}.scope")
    if cap.model_extra:
        raise AdCPValidationError(field=f"{field}.{next(iter(cap.model_extra))}")
    if cap.per is not None and cap.per.value not in {"devices", "cookies"}:
        raise AdCPValidationError(field=f"{field}.per")
    caps = []
    if cap.max_impressions is not None:
        if cap.per is None or cap.window is None:
            raise AdCPValidationError(field=f"{field}.{'per' if cap.per is None else 'window'}")
        if cap.max_impressions > 2_147_483_647:
            raise AdCPValidationError(field=f"{field}.max_impressions")
        caps.append(_duration_cap(cap.max_impressions, cap.window, f"{field}.window", for_forecast=for_forecast))
    elif cap.per is not None or cap.window is not None:
        raise AdCPValidationError(field=f"{field}.max_impressions")
    caps.extend(_suppression_frequency_caps(cap, field, for_forecast=for_forecast))
    if cap.suppress is None and cap.suppress_minutes is None and cap.max_impressions is None:
        raise AdCPValidationError(field=field)
    return caps


def _suppression_frequency_caps(cap: FrequencyCap, field: str, *, for_forecast: bool) -> list[dict[str, Any]]:
    if cap.suppress is not None:
        suppression = _duration_cap(1, cap.suppress, f"{field}.suppress", for_forecast=for_forecast)
        if cap.suppress_minutes is not None:
            legacy = _minute_cap(1, cap.suppress_minutes, f"{field}.suppress_minutes")
            if suppression != legacy:
                raise AdCPValidationError(field=f"{field}.suppress_minutes")
        return [suppression]
    elif cap.suppress_minutes is not None and cap.suppress_minutes != 0:
        return [_minute_cap(1, cap.suppress_minutes, f"{field}.suppress_minutes")]
    return []


def _duration_cap(impressions: int, duration: Duration, field: str, *, for_forecast: bool) -> dict[str, Any]:
    if duration.unit.value == "campaign":
        if for_forecast or duration.interval != 1 or field.endswith(".suppress"):
            raise AdCPValidationError(field=field)
        return {"maxImpressions": impressions, "numTimeUnits": 1, "timeUnit": "LIFETIME"}
    if duration.unit.value == "seconds":
        minutes, remainder = divmod(duration.interval, 60)
        if remainder:
            raise AdCPValidationError(field=field)
    else:
        minutes = duration.interval * {"minutes": 1, "hours": 60, "days": 1440}[duration.unit.value]
    return _minute_cap(impressions, minutes, field)


def _minute_cap(impressions: int, minutes: float, field: str) -> dict[str, Any]:
    if minutes <= 0 or not float(minutes).is_integer():
        raise AdCPValidationError(field=field)
    for unit in ("DAY", "HOUR", "MINUTE"):
        divisor = _MINUTES_PER_UNIT[unit]
        if minutes % divisor == 0:
            interval = int(minutes / divisor)
            if interval > 2_147_483_647:
                raise AdCPValidationError(field=field)
            return {"maxImpressions": impressions, "numTimeUnits": interval, "timeUnit": unit}
    raise AdCPValidationError(field=field)


def _merge_frequency_caps(caps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for cap in caps:
        for existing in merged:
            same_unit = cap["timeUnit"] == existing["timeUnit"]
            same_range = same_unit and cap["numTimeUnits"] == existing["numTimeUnits"]
            if cap["timeUnit"] in _MINUTES_PER_UNIT and existing["timeUnit"] in _MINUTES_PER_UNIT:
                same_range = (
                    cap["numTimeUnits"] * _MINUTES_PER_UNIT[cap["timeUnit"]]
                    == existing["numTimeUnits"] * _MINUTES_PER_UNIT[existing["timeUnit"]]
                )
            if same_range:
                existing["maxImpressions"] = min(existing["maxImpressions"], cap["maxImpressions"])
                break
        else:
            if any(cap["timeUnit"] == existing["timeUnit"] for existing in merged):
                raise AdCPValidationError(field="targeting_overlay.frequency_cap")
            merged.append(cap)
    if len(merged) > 10:
        raise AdCPValidationError(field="frequency_caps")
    return merged
