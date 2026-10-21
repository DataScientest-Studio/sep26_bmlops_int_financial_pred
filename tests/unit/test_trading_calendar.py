"""Unit tests of the trading calendar."""

from datetime import date, datetime

import pytest

from forecasting.trading_calendar import (
    is_trading_day,
    next_trading_day,
    session_close,
    trading_days,
)


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
    """The close of that day's session, early closes included."""
    assert session_close(exchange, day) == datetime.fromisoformat(expected)


@pytest.mark.parametrize(
    ("exchange", "day", "expected"),
    [
        ("XNYS", date(2026, 12, 25), False),  # Christmas
        ("XNYS", date(2026, 10, 10), False),  # Saturday
        ("XETR", date(2026, 12, 24), False),  # Christmas Eve, Xetra closed
    ],
)
def test_trading_day_follows_the_exchange(exchange, day, expected):
    """Weekends and exchange holidays are no trading days."""
    assert is_trading_day(exchange, day) is expected


@pytest.mark.parametrize(
    ("exchange", "day", "expected"),
    [
        ("XNYS", date(2026, 10, 9), date(2026, 10, 12)),  # Friday to Monday
        ("XNYS", date(2026, 11, 25), date(2026, 11, 27)),  # skips Thanksgiving
        ("XETR", date(2026, 12, 23), date(2026, 12, 28)),  # skips Christmas
        ("XNYS", date(2026, 10, 10), date(2026, 10, 12)),  # from a Saturday
    ],
)
def test_next_trading_day_skips_closed_days(exchange, day, expected):
    """The next trading day skips weekends and holidays."""
    assert next_trading_day(exchange, day) == expected


def test_trading_days_leave_out_holidays():
    """A week with a holiday has only its sessions."""
    days = trading_days("XNYS", date(2026, 11, 23), date(2026, 11, 29))
    assert days == [
        date(2026, 11, 23),
        date(2026, 11, 24),
        date(2026, 11, 25),
        date(2026, 11, 27),
    ]
