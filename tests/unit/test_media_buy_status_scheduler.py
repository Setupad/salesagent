"""Unit tests for media buy status scheduler transition decisions."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from src.core.database.models import PersistedMediaBuyStatus
from src.services.media_buy_status_scheduler import MediaBuyStatusScheduler


def _media_buy(status: str, *, start_time: datetime, end_time: datetime) -> MagicMock:
    media_buy = MagicMock()
    media_buy.media_buy_id = "mb_1"
    media_buy.tenant_id = "tenant_1"
    media_buy.status = status
    media_buy.start_time = start_time
    media_buy.end_time = end_time
    media_buy.start_date = start_time.date()
    media_buy.end_date = end_time.date()
    return media_buy


def test_pending_creatives_without_assignments_stays_held():
    scheduler = MediaBuyStatusScheduler()
    scheduler._has_creative_assignments = MagicMock(return_value=False)
    scheduler._are_creatives_approved = MagicMock(return_value=True)
    now = datetime.now(UTC)
    media_buy = _media_buy(
        "pending_creatives",
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(days=1),
    )

    assert scheduler._compute_new_status(media_buy, now, MagicMock()) is None
    scheduler._are_creatives_approved.assert_not_called()


def test_pending_creatives_with_approved_assignments_can_activate():
    scheduler = MediaBuyStatusScheduler()
    scheduler._has_creative_assignments = MagicMock(return_value=True)
    scheduler._are_creatives_approved = MagicMock(return_value=True)
    now = datetime.now(UTC)
    media_buy = _media_buy(
        "pending_creatives",
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(days=1),
    )

    assert scheduler._compute_new_status(media_buy, now, MagicMock()) == PersistedMediaBuyStatus.ACTIVE
