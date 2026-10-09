"""Acceptance tests of the data requirements (black box)."""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from forecasting.load import load_history
from forecasting.trading_calendar import (
    is_trading_day,
    next_trading_day,
    trading_days,
)
from tests.fakes import SECURITIES, FakeSource, price_history, standard_source

pytestmark = pytest.mark.acceptance


def stored_rows(engine, symbol: str) -> pd.DataFrame:
    """Read the stored prices of one security straight from the table."""
    query = text("SELECT * FROM prices WHERE symbol = :symbol ORDER BY day")
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params={"symbol": symbol})


def test_load_stores_complete_history_of_each_security(engine):
    """REQ-DAT-001: one run stores every delivered day of every security."""
    source = standard_source()
    report = load_history(engine, source, SECURITIES)
    total = 0
    for security in SECURITIES:
        delivered = source.histories[security.symbol]
        stored = stored_rows(engine, security.symbol)
        assert list(stored["day"]) == list(delivered["day"])
        assert np.allclose(stored["close"].astype(float), delivered["close"])
        total += len(delivered)
    assert report.stored == total
    assert report.rejected == 0


def test_repeated_load_adds_no_duplicates(engine):
    """REQ-DAT-001: loading the same history twice keeps one row per day."""
    source = standard_source()
    first = load_history(engine, source, SECURITIES)
    second = load_history(engine, source, SECURITIES)
    stored = sum(len(stored_rows(engine, s.symbol)) for s in SECURITIES)
    assert stored == first.stored
    assert second.stored == 0


def test_invalid_quotes_are_rejected_and_counted(engine):
    """REQ-DAT-005: missing field, non-positive price, duplicate day are refused."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    valid_days = len(history)
    history.loc[3, "close"] = None
    history.loc[5, "open"] = -1.0
    history = pd.concat([history, history.iloc[[10]]], ignore_index=True)
    report = load_history(engine, FakeSource({security.symbol: history}), (security,))
    stored = stored_rows(engine, security.symbol)
    assert report.rejected == 3
    assert report.stored == valid_days - 2
    assert len(stored) == valid_days - 2
    assert stored["day"].is_unique


@pytest.mark.parametrize(
    ("exchange", "day", "expected"),
    [
        ("XNYS", date(2026, 12, 25), False),  # Christmas
        ("XNYS", date(2026, 12, 24), True),  # early close, still a session
        ("XNYS", date(2026, 10, 10), False),  # Saturday
        ("XETR", date(2026, 12, 24), False),  # Christmas Eve, Xetra closed
    ],
)
def test_trading_day_follows_the_exchange(exchange, day, expected):
    """REQ-DAT-004: weekends and exchange holidays are no trading days."""
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
    """REQ-DAT-004: the next trading day skips weekends and holidays."""
    assert next_trading_day(exchange, day) == expected


def test_trading_days_leave_out_holidays():
    """REQ-DAT-004: a week with a holiday has only its sessions."""
    days = trading_days("XNYS", date(2026, 11, 23), date(2026, 11, 29))
    assert days == [
        date(2026, 11, 23),
        date(2026, 11, 24),
        date(2026, 11, 25),
        date(2026, 11, 27),
    ]
