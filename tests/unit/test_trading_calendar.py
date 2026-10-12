"""Trading calendar behaviour the acceptance tests do not cover."""

from datetime import date

import pytest
from exchange_calendars.errors import DateOutOfBounds

from forecasting.trading_calendar import is_trading_day


def test_date_outside_the_calendar_raises():
    """REQ-DAT-004: a date outside the calendar's range raises, never guesses."""
    # A real NYSE trading day, so only the range can cause the error; a past date,
    # because the calendar's range moves forward and would catch up with a future one.
    with pytest.raises(DateOutOfBounds):
        is_trading_day("XNYS", date(1990, 1, 2))
