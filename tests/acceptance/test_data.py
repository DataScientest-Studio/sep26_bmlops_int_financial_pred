"""Acceptance tests of the data requirements (black box)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from forecasting.load import load_history
from forecasting.trading_calendar import (
    is_trading_day,
    next_trading_day,
    session_close,
    trading_days,
)
from tests.fakes import (
    SECURITIES,
    FakeSource,
    price_history,
    standard_source,
)

pytestmark = pytest.mark.acceptance


def stored_rows(engine, symbol: str) -> pd.DataFrame:
    """Read the stored prices of one security straight from the table."""
    query = text("SELECT * FROM prices WHERE symbol = :symbol ORDER BY day")
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params={"symbol": symbol})


def test_load_stores_complete_history_of_each_security(engine, settings):
    """REQ-DAT-001: one run stores every delivered day of every security."""
    source = standard_source()
    report = load_history(engine, source, SECURITIES, settings.final_delay)
    total = 0
    for security in SECURITIES:
        delivered = source.histories[security.symbol]
        stored = stored_rows(engine, security.symbol)
        assert list(stored["day"]) == list(delivered["day"])
        assert np.allclose(stored["close"].astype(float), delivered["close"])
        total += len(delivered)
    assert report.stored == total
    assert report.rejected == 0


def test_repeated_load_adds_no_duplicates(engine, settings):
    """REQ-DAT-001: loading the same history twice keeps one row per day."""
    source = standard_source()
    first = load_history(engine, source, SECURITIES, settings.final_delay)
    second = load_history(engine, source, SECURITIES, settings.final_delay)
    stored = sum(len(stored_rows(engine, s.symbol)) for s in SECURITIES)
    assert stored == first.stored
    assert second.stored == 0


def test_invalid_quotes_are_rejected_and_counted(engine, settings):
    """REQ-DAT-005: missing field, non-positive price, duplicate day are refused."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    valid_days = len(history)
    history.loc[3, "close"] = None
    history.loc[5, "open"] = -1.0
    history = pd.concat([history, history.iloc[[10]]], ignore_index=True)
    source = FakeSource({security.symbol: history})
    report = load_history(engine, source, (security,), settings.final_delay)
    stored = stored_rows(engine, security.symbol)
    assert report.rejected == 3
    assert report.stored == valid_days - 2
    assert len(stored) == valid_days - 2
    assert stored["day"].is_unique


def last_row(engine, symbol: str) -> pd.Series:
    """Read the stored quote of the latest day of one security."""
    return stored_rows(engine, symbol).iloc[-1]


def test_provisional_close_is_replaced_by_a_later_fetch(engine, settings):
    """REQ-DAT-007: a quote fetched during the session is replaced after the close."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    final_from = session_close(security.exchange, date(2025, 12, 30))
    final_from += settings.final_delay
    source = FakeSource({security.symbol: history}, final_from - timedelta(hours=1))
    load_history(engine, source, (security,), settings.final_delay)
    history.loc[history.index[-1], "close"] += 1.0
    source.fetched_at = final_from
    report = load_history(engine, source, (security,), settings.final_delay)
    latest = last_row(engine, security.symbol)
    assert report.replaced == 1
    assert report.stored == 0
    assert float(latest["close"]) == pytest.approx(history["close"].iloc[-1])
    assert latest["fetched_at"] == final_from
    assert len(stored_rows(engine, security.symbol)) == len(history)


def test_older_fetch_does_not_replace_a_newer_provisional_close(engine, settings):
    """REQ-DAT-007: only a later fetch replaces a provisional quote."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    newer_close = history["close"].iloc[-1]
    final_from = session_close(security.exchange, date(2025, 12, 30))
    final_from += settings.final_delay
    newer = final_from - timedelta(hours=1)
    source = FakeSource({security.symbol: history}, newer)
    load_history(engine, source, (security,), settings.final_delay)
    older = history.assign(close=history["close"] + 1.0)
    source = FakeSource({security.symbol: older}, newer - timedelta(hours=1))
    report = load_history(engine, source, (security,), settings.final_delay)
    latest = last_row(engine, security.symbol)
    assert report.replaced == 0
    assert float(latest["close"]) == pytest.approx(newer_close)
    assert latest["fetched_at"] == newer


def test_final_close_is_never_replaced(engine, settings):
    """REQ-DAT-007: a quote fetched at the close plus the delay is final."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    first_close = history["close"].iloc[-1]
    final_from = session_close(security.exchange, date(2025, 12, 30))
    final_from += settings.final_delay
    source = FakeSource({security.symbol: history}, final_from)
    load_history(engine, source, (security,), settings.final_delay)
    history.loc[history.index[-1], "close"] += 1.0
    source.fetched_at = final_from + timedelta(days=1)
    report = load_history(engine, source, (security,), settings.final_delay)
    latest = last_row(engine, security.symbol)
    assert report.replaced == 0
    assert float(latest["close"]) == pytest.approx(first_close)
    assert latest["fetched_at"] == final_from


def test_final_close_survives_a_delivery_with_days_as_text(engine, settings):
    """REQ-DAT-007: a final quote is kept even if a source spells its day as text."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    first_close = history["close"].iloc[-1]
    final_from = session_close(security.exchange, date(2025, 12, 30))
    final_from += settings.final_delay
    source = FakeSource({security.symbol: history}, final_from)
    load_history(engine, source, (security,), settings.final_delay)
    as_text = history.assign(day=history["day"].map(date.isoformat), close=1.0)
    source = FakeSource({security.symbol: as_text}, final_from + timedelta(days=1))
    load_history(engine, source, (security,), settings.final_delay)
    latest = last_row(engine, security.symbol)
    assert float(latest["close"]) == pytest.approx(first_close)
    assert latest["fetched_at"] == final_from


def test_early_close_makes_a_quote_final_sooner(engine, settings):
    """REQ-DAT-007: the delay counts from the exchange's real close of that day."""
    security = SECURITIES[0]  # XNYS: early close on 2025-11-28
    history = price_history(security.exchange, "2025-11-01", "2025-11-28", seed=4)
    first_close = history["close"].iloc[-1]
    final_from = session_close(security.exchange, date(2025, 11, 28))
    final_from += settings.final_delay
    source = FakeSource({security.symbol: history}, final_from)
    load_history(engine, source, (security,), settings.final_delay)
    history.loc[history.index[-1], "close"] += 1.0
    source.fetched_at = final_from + timedelta(days=3)
    report = load_history(engine, source, (security,), settings.final_delay)
    assert report.replaced == 0
    assert float(last_row(engine, security.symbol)["close"]) == pytest.approx(
        first_close
    )


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
