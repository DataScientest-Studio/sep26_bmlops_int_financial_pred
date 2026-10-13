"""Acceptance tests of the data requirements (black box)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from forecasting.load import load_history
from forecasting.trading_calendar import session_close
from tests.fakes import (
    INDICES,
    SECURITIES,
    FakeSource,
    price_history,
    standard_source,
)

pytestmark = pytest.mark.acceptance


def _stored_rows(engine, symbol: str) -> pd.DataFrame:
    """Read the stored prices of one symbol straight from the table."""
    query = text("SELECT * FROM prices WHERE symbol = :symbol ORDER BY day")
    with engine.connect() as connection:
        return pd.read_sql(query, connection, params={"symbol": symbol})


def _stored_events(engine, table: str) -> pd.DataFrame:
    """Read all stored events of one table (splits or dividends) straight from it."""
    query = text(f"SELECT * FROM {table} ORDER BY symbol, day")
    with engine.connect() as connection:
        return pd.read_sql(query, connection)


def _last_row(engine, symbol: str) -> pd.Series:
    """Read the stored quote of the latest day of one symbol."""
    return _stored_rows(engine, symbol).iloc[-1]


def test_load_stores_the_history_of_each_security_and_index(engine, settings):
    """REQ-DAT-001: one run stores every delivered day of every security and index."""
    source = standard_source()
    load_history(
        engine,
        source,
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    for security in SECURITIES + INDICES:
        delivered = source.histories[security.symbol]
        stored = _stored_rows(engine, security.symbol)
        assert list(stored["day"]) == list(delivered["day"])
        assert np.allclose(stored["close"].astype(float), delivered["close"])


def test_load_stores_splits_and_dividends_of_each_security(engine, settings):
    """REQ-DAT-001: one run stores each security's splits and dividends."""
    splits = {"TEST.US": pd.DataFrame({"day": [date(2025, 6, 2)], "ratio": [4.0]})}
    dividends = {
        "TEST.US": pd.DataFrame(
            {"day": [date(2025, 3, 14)], "amount": [0.25], "currency": ["USD"]}
        ),
        "TEST.DE": pd.DataFrame(
            {"day": [date(2025, 5, 15)], "amount": [2.35], "currency": ["EUR"]}
        ),
    }
    source = standard_source(splits=splits, dividends=dividends)
    load_history(
        engine,
        source,
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    stored_splits = _stored_events(engine, "splits")
    stored_dividends = _stored_events(engine, "dividends")
    assert list(stored_splits["symbol"]) == ["TEST.US"]
    assert list(stored_splits["day"]) == [date(2025, 6, 2)]
    assert list(stored_splits["ratio"].astype(float)) == [4.0]
    assert list(stored_dividends["symbol"]) == ["TEST.DE", "TEST.US"]
    assert list(stored_dividends["amount"].astype(float)) == [2.35, 0.25]
    assert list(stored_dividends["currency"]) == ["EUR", "USD"]


def test_first_load_asks_from_the_configured_first_day(engine, settings):
    """REQ-DAT-001: with nothing stored, the history is asked for from the first day."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    source = FakeSource({security.symbol: history})
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    assert source.starts[security.symbol] == settings.history_start


def test_load_undoes_the_split_correction_of_volumes(engine, settings):
    """REQ-DAT-001: volumes corrected for later splits are stored as traded."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    history["volume"] = 6_000
    history.loc[0, "volume"] = 6_004
    splits = pd.DataFrame(
        {"day": [date(2025, 2, 3), date(2025, 3, 3)], "ratio": [2.0, 3.0]}
    )
    source = FakeSource({security.symbol: history}, splits={security.symbol: splits})
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    volume = _stored_rows(engine, security.symbol).set_index("day")["volume"]
    assert volume[date(2025, 1, 2)] == 1_001  # both splits undone: 6_004 / 6, rounded
    assert volume[date(2025, 2, 3)] == 2_000  # only the March split undone


def test_load_keeps_volumes_of_a_split_after_the_last_delivered_day(engine, settings):
    """REQ-DAT-001: a split announced for a later day leaves the volumes as traded."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    history["volume"] = 6_000
    splits = pd.DataFrame({"day": [date(2025, 4, 1)], "ratio": [0.05]})
    source = FakeSource({security.symbol: history}, splits={security.symbol: splits})
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    volume = _stored_rows(engine, security.symbol)["volume"]
    assert list(volume) == [6_000] * len(history)


def test_load_undoes_a_split_on_the_last_delivered_day(engine, settings):
    """REQ-DAT-001: a split counts from its delivered day, even a refused one."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    history["volume"] = 6_000
    history.loc[history.index[-1], "open"] = 0.0
    splits = pd.DataFrame({"day": [date(2025, 3, 31)], "ratio": [2.0]})
    source = FakeSource({security.symbol: history}, splits={security.symbol: splits})
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    volume = _stored_rows(engine, security.symbol)["volume"]
    assert list(volume) == [3_000] * (len(history) - 1)  # the split day is rejected


def test_update_asks_from_the_latest_stored_day(engine, settings):
    """REQ-DAT-002: a later run asks only for the days from the latest stored one on."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    source = FakeSource({security.symbol: history})
    for _ in range(2):
        load_history(
            engine,
            source,
            (security,),
            (),
            settings.final_delay,
            settings.history_start,
        )
    assert source.starts[security.symbol] == date(2025, 3, 31)


def test_missing_trading_days_are_counted(engine, settings):
    """REQ-DAT-004: only trading days without a quote count as missing."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    history = history.drop(index=20)
    source = FakeSource({security.symbol: history})
    report = load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    assert report.missing == 1


def test_invalid_quotes_are_rejected_and_counted(engine, settings):
    """REQ-DAT-005: missing field, non-positive price, duplicate day are refused."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    valid_days = len(history)
    history.loc[3, "close"] = None
    history.loc[5, "open"] = -1.0
    history = pd.concat([history, history.iloc[[10]]], ignore_index=True)
    source = FakeSource({security.symbol: history})
    report = load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    stored = _stored_rows(engine, security.symbol)
    assert report.rejected == 3
    assert len(stored) == valid_days - 2


def test_negative_volume_and_closed_days_are_rejected_and_counted(engine, settings):
    """REQ-DAT-005: a negative volume or a day that is not a trading day is refused."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    valid_days = len(history)
    history.loc[5, "volume"] = -100
    saturday = history.iloc[[10]].assign(day=date(2025, 1, 4))
    history = pd.concat([history, saturday], ignore_index=True)
    source = FakeSource({security.symbol: history})
    report = load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    stored = _stored_rows(engine, security.symbol)
    assert report.rejected == 2
    assert len(stored) == valid_days - 1


def test_invalid_splits_and_dividends_are_rejected_and_counted(engine, settings):
    """REQ-DAT-005: incomplete, non-positive or repeated events are refused."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-03-31", seed=7)
    splits = pd.DataFrame(
        {
            "day": [
                date(2025, 1, 6),
                date(2025, 1, 7),
                date(2025, 1, 8),
                date(2025, 1, 6),
            ],
            "ratio": [2.0, None, 0.0, 3.0],
        }
    )
    dividends = pd.DataFrame(
        {
            "day": [
                date(2025, 1, 15),
                date(2025, 1, 16),
                date(2025, 1, 17),
                date(2025, 1, 15),
            ],
            "amount": [0.25, -0.1, 0.30, 0.25],
            "currency": ["USD", "USD", None, "USD"],
        }
    )
    source = FakeSource(
        {security.symbol: history},
        splits={security.symbol: splits},
        dividends={security.symbol: dividends},
    )
    report = load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    stored_splits = _stored_events(engine, "splits")
    stored_dividends = _stored_events(engine, "dividends")
    assert report.rejected == 6
    assert list(stored_splits["day"]) == [date(2025, 1, 6)]
    assert list(stored_splits["ratio"].astype(float)) == [2.0]
    assert list(stored_dividends["day"]) == [date(2025, 1, 15)]


def test_provisional_close_is_replaced_by_a_later_fetch(engine, settings):
    """REQ-DAT-007: a quote fetched during the session is replaced after the close."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    final_from = session_close(security.exchange, date(2025, 12, 30))
    final_from += settings.final_delay
    source = FakeSource({security.symbol: history}, final_from - timedelta(hours=1))
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    history.loc[history.index[-1], "close"] += 1.0
    source.fetched_at = final_from
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    latest = _last_row(engine, security.symbol)
    assert float(latest["close"]) == pytest.approx(history["close"].iloc[-1])
    assert latest["fetched_at"] == final_from


def test_older_fetch_does_not_replace_a_newer_provisional_close(engine, settings):
    """REQ-DAT-007: only a later fetch replaces a provisional quote."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    newer_close = history["close"].iloc[-1]
    final_from = session_close(security.exchange, date(2025, 12, 30))
    final_from += settings.final_delay
    newer = final_from - timedelta(hours=1)
    source = FakeSource({security.symbol: history}, newer)
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    older = history.assign(close=history["close"] + 1.0)
    source = FakeSource({security.symbol: older}, newer - timedelta(hours=1))
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    latest = _last_row(engine, security.symbol)
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
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    history.loc[history.index[-1], "close"] += 1.0
    source.fetched_at = final_from + timedelta(days=1)
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    latest = _last_row(engine, security.symbol)
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
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    history.loc[history.index[-1], "close"] += 1.0
    source.fetched_at = final_from + timedelta(days=3)
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    assert float(_last_row(engine, security.symbol)["close"]) == pytest.approx(
        first_close
    )
