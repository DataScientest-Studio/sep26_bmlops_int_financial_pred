"""Unit tests of the rule that tells provisional from final quotes."""

from datetime import date, timedelta

import pytest

from forecasting.load import is_final
from forecasting.trading_calendar import session_close


@pytest.mark.parametrize(
    ("exchange", "day", "offset", "expected"),
    [
        ("XNYS", date(2025, 12, 30), timedelta(seconds=-1), False),
        ("XNYS", date(2025, 12, 30), timedelta(0), True),
        ("XNYS", date(2025, 11, 28), timedelta(0), True),  # early close
        ("XETR", date(2025, 12, 29), timedelta(seconds=-1), False),
        ("XETR", date(2025, 12, 29), timedelta(0), True),
        ("XNYS", date(2025, 12, 29), timedelta(hours=12), True),  # next morning
    ],
)
def test_quote_is_final_from_close_plus_delay(
    example_settings, exchange, day, offset, expected
):
    """REQ-DAT-007: final from the exchange's close of that day plus the delay."""
    delay = example_settings.final_delay
    fetched_at = session_close(exchange, day) + delay + offset
    assert is_final(exchange, day, fetched_at, delay) is expected
