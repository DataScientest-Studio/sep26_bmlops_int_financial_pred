"""Unit tests of the numbers the API reports to Prometheus."""

from datetime import date, timedelta

import pytest

from forecasting.api.metrics import trading_days_behind
from forecasting.trading_calendar import session_close


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
