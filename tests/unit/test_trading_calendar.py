"""Trading calendar behaviour the acceptance tests do not cover."""

from datetime import date, datetime

import pytest
from exchange_calendars.errors import DateOutOfBounds

from forecasting.trading_calendar import is_trading_day, session_close


def test_date_outside_the_calendar_raises():
    """REQ-DAT-004: a date outside the calendar's range raises, never guesses."""
    # A real NYSE trading day, so only the range can cause the error; a past date,
    # because the calendar's range moves forward and would catch up with a future one.
    with pytest.raises(DateOutOfBounds):
        is_trading_day("XNYS", date(1990, 1, 2))


@pytest.mark.parametrize(
    ("exchange", "day", "expected"),
    [
        ("XNYS", date(2025, 12, 30), "2025-12-30T21:00:00+00:00"),  # 16:00 New York
        ("XNYS", date(2025, 11, 28), "2025-11-28T18:00:00+00:00"),  # early close
        ("XNYS", date(2025, 7, 1), "2025-07-01T20:00:00+00:00"),  # summer time
        ("XETR", date(2025, 12, 29), "2025-12-29T16:30:00+00:00"),  # 17:30 Frankfurt
    ],
)
def test_session_close_is_the_exchange_close_in_utc(exchange, day, expected):
    """REQ-DAT-007: the close of that day's session, early closes included."""
    assert session_close(exchange, day) == datetime.fromisoformat(expected)
