import pytest
from adcp.types import DaypartTarget

from src.adapters.gam.managers.targeting import build_daypart_targeting
from src.core.exceptions import AdCPValidationError


def test_friday_lunchtime():
    assert build_daypart_targeting([DaypartTarget(days=["friday"], start_hour=12, end_hour=14)]) == {
        "timeZone": "PUBLISHER",
        "dayParts": [
            {
                "dayOfWeek": "FRIDAY",
                "startTime": {"hour": 12, "minute": "ZERO"},
                "endTime": {"hour": 14, "minute": "ZERO"},
            }
        ],
    }


def test_multiple_days_and_full_day():
    result = build_daypart_targeting([DaypartTarget(days=["monday", "friday"], start_hour=0, end_hour=24)])
    assert [part["dayOfWeek"] for part in result["dayParts"]] == ["MONDAY", "FRIDAY"]
    assert all(part["startTime"] == {"hour": 0, "minute": "ZERO"} for part in result["dayParts"])
    assert all(part["endTime"] == {"hour": 24, "minute": "ZERO"} for part in result["dayParts"])


def test_overlapping_and_duplicate_windows_are_merged():
    windows = [
        DaypartTarget(days=["friday", "friday"], start_hour=12, end_hour=14),
        DaypartTarget(days=["friday"], start_hour=13, end_hour=16),
        DaypartTarget(days=["friday"], start_hour=18, end_hour=20),
    ]
    result = build_daypart_targeting(windows)
    assert [(part["startTime"]["hour"], part["endTime"]["hour"]) for part in result["dayParts"]] == [
        (12, 16),
        (18, 20),
    ]


@pytest.mark.parametrize("start_hour,end_hour", [(12, 12), (18, 6)])
def test_invalid_window_is_rejected(start_hour, end_hour):
    with pytest.raises(AdCPValidationError) as error:
        build_daypart_targeting([DaypartTarget(days=["friday"], start_hour=start_hour, end_hour=end_hour)])
    assert error.value.field == "targeting_overlay.daypart_targets[0].end_hour"


def test_absent_windows_leave_targeting_unrestricted():
    assert build_daypart_targeting(None) == {}
