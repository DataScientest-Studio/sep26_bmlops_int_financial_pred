"""Unit tests of the numbers the API reports to Prometheus."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from forecasting.api.metrics import daily_updates_missed, trading_days_behind
from forecasting.config import DailyUpdate
from forecasting.trading_calendar import session_close

NEW_YORK = ZoneInfo("America/New_York")
# Weekdays from 16:00 New York: with the final delay a load is due at 16:25, and its
# load limit passes at 16:55.
DAILY_UPDATE = DailyUpdate(
    (1, 2, 3, 4, 5), NEW_YORK, time(16, 0), timedelta(minutes=30)
)
FINAL_DELAY = timedelta(minutes=25)


@pytest.mark.parametrize(
    ("latest_day", "due_day", "offset", "expected"),
    [
        (date(2025, 12, 30), date(2025, 12, 31), timedelta(seconds=-1), 0),
        (date(2025, 12, 30), date(2025, 12, 31), timedelta(0), 1),
        (date(2025, 12, 24), date(2025, 12, 29), timedelta(0), 2),
    ],
)
def test_only_trading_days_final_at_the_load_count_as_behind(
    example_settings, latest_day, due_day, offset, expected
):
    """Counts only trading days final when the latest load ran, skipping holidays."""
    delay = example_settings.final_delay
    fetched_at = session_close("XNYS", due_day) + delay + offset
    assert trading_days_behind("XNYS", latest_day, fetched_at, delay) == expected


@pytest.mark.parametrize(
    ("latest_load", "now", "expected"),
    [
        # Loaded after Tuesday's due time:
        ("2026-11-03 16:26", "2026-11-03 17:00", 0),
        # Tuesday's load limit not yet passed:
        ("2026-11-02 16:26", "2026-11-03 16:54:59", 0),
        # Tuesday's load limit passed:
        ("2026-11-02 16:26", "2026-11-03 16:55", 1),
        # Loaded on Friday; the weekend is not scheduled:
        ("2026-10-30 16:26", "2026-11-02 16:55", 1),
    ],
)
def test_only_scheduled_daily_updates_past_their_load_limit_count_as_missed(
    latest_load, now, expected
):
    """Counts scheduled daily updates after the latest load past their load limit."""
    loaded_at = datetime.fromisoformat(latest_load).replace(tzinfo=NEW_YORK)
    counted_at = datetime.fromisoformat(now).replace(tzinfo=NEW_YORK)
    missed = daily_updates_missed(loaded_at, counted_at, DAILY_UPDATE, FINAL_DELAY)
    assert missed == expected
