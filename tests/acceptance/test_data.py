"""Acceptance tests of the data requirements (black box)."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import text

from forecasting.datasets import dataset_version
from forecasting.db import connect, read_prices
from forecasting.load import load_history
from forecasting.replay import replay_next_day
from forecasting.trading_calendar import session_close, trading_days
from tests.acceptance.tables import load_history_around_start, stored_table
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


def _last_row(engine, symbol: str) -> pd.Series:
    """Read the stored quote of the latest day of one symbol."""
    return _stored_rows(engine, symbol).iloc[-1]


def _training_rows(engine, settings) -> pd.DataFrame:
    """Load the standard history; read one security's prices as training does."""
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )

    return read_prices(engine, SECURITIES[0].symbol)


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
    stored_splits = stored_table(engine, "splits")
    stored_dividends = stored_table(engine, "dividends")
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
    stored_splits = stored_table(engine, "splits")
    stored_dividends = stored_table(engine, "dividends")
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


def test_first_replay_copies_the_history_up_to_the_start_day(
    engine, settings, replay_url
):
    """REQ-DAT-003: the first run copies every stored row up to the start, unchanged."""
    load_history_around_start(engine, settings)
    replay_next_day(engine, replay_url, settings.replay_start)
    replay_engine = connect(replay_url)
    for table in ["prices", "splits", "dividends"]:
        stored = stored_table(engine, table)
        expected = stored[stored["day"] <= settings.replay_start]
        replayed = stored_table(replay_engine, table)
        pd.testing.assert_frame_equal(replayed, expected.reset_index(drop=True))
    replay_engine.dispose()


def test_each_later_replay_adds_the_next_stored_day(engine, settings, replay_url):
    """REQ-DAT-003: each later run copies the next stored day."""
    load_history_around_start(engine, settings)
    securities = SECURITIES + INDICES
    first = settings.replay_start + timedelta(days=1)
    last = settings.replay_start + timedelta(days=30)
    open_days = sorted(
        {day for s in securities for day in trading_days(s.exchange, first, last)}
    )
    replay_next_day(engine, replay_url, settings.replay_start)
    replayed_days = [
        replay_next_day(engine, replay_url, settings.replay_start) for _ in open_days
    ]
    assert replayed_days == open_days
    replay_engine = connect(replay_url)
    for table in ["prices", "splits", "dividends"]:
        replayed = stored_table(replay_engine, table)
        pd.testing.assert_frame_equal(replayed, stored_table(engine, table))
    replay_engine.dispose()


def test_replay_takes_over_the_final_quote_of_a_replayed_provisional_day(
    engine, settings, replay_url
):
    """REQ-DAT-003: a day replayed while provisional is replayed again once final."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    provisional_day = history["day"].iloc[-2]
    closing_time = session_close(security.exchange, provisional_day)
    source = FakeSource({security.symbol: history.head(-1)}, closing_time)
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    replay_next_day(engine, replay_url, provisional_day)
    source.histories[security.symbol] = history
    source.fetched_at = session_close(security.exchange, history["day"].iloc[-1])
    source.fetched_at += settings.final_delay
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    replay_next_day(engine, replay_url, provisional_day)
    replay_engine = connect(replay_url)
    replayed = _stored_rows(replay_engine, security.symbol)
    replay_engine.dispose()
    pd.testing.assert_frame_equal(replayed, _stored_rows(engine, security.symbol))


def test_replay_passes_a_trading_day_without_stored_prices(
    engine, settings, replay_url
):
    """REQ-DAT-003: a trading day with no stored prices does not stop the replay."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-01", "2025-12-30", seed=3)
    start, after_gap = history["day"].iloc[-3], history["day"].iloc[-1]
    source = FakeSource({security.symbol: history.drop(index=history.index[-2])})
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    replay_next_day(engine, replay_url, start)
    assert replay_next_day(engine, replay_url, start) == after_gap


@pytest.mark.parametrize("edge", [min, max])
def test_replay_starts_on_the_first_or_latest_stored_day(
    engine, settings, replay_url, edge
):
    """REQ-DAT-003: the replay may start on the first or the latest stored day."""
    start = edge(load_history_around_start(engine, settings))
    assert replay_next_day(engine, replay_url, start) == start


@pytest.mark.parametrize("edge, shift", [(min, -1), (max, 1)])
def test_replay_start_outside_the_stored_days_is_refused(
    engine, settings, replay_url, edge, shift
):
    """REQ-DAT-003: a start before the first or after the latest day is refused."""
    start = edge(load_history_around_start(engine, settings))
    start += timedelta(days=shift)
    with pytest.raises(ValueError):
        replay_next_day(engine, replay_url, start)


def test_replay_at_the_latest_stored_day_has_nothing_left(engine, settings, replay_url):
    """REQ-DAT-003: once the latest stored day is copied, nothing is left to replay."""
    latest = max(load_history_around_start(engine, settings))
    replay_next_day(engine, replay_url, latest)
    assert replay_next_day(engine, replay_url, latest) is None


def test_replay_with_nothing_stored_is_refused(engine, settings, replay_url):
    """REQ-DAT-003: with no stored history, there is nothing to replay."""
    with pytest.raises(ValueError):
        replay_next_day(engine, replay_url, settings.replay_start)


def test_same_training_rows_get_the_same_version(engine, settings):
    """REQ-DAT-006: the same training rows always get the same version identifier."""
    rows = _training_rows(engine, settings)
    symbol = SECURITIES[0].symbol
    first = dataset_version(settings, symbol, rows)
    read_again = read_prices(engine, symbol)
    assert dataset_version(settings, symbol, read_again) == first


def test_changed_training_rows_get_a_new_version(engine, settings):
    """REQ-DAT-006: changed training rows get a new version identifier."""
    rows = _training_rows(engine, settings)
    symbol = SECURITIES[0].symbol
    first = dataset_version(settings, symbol, rows)
    # Changes one close in the middle of the history by one cent, so the rows differ
    # from the first version only in that price: the same days and number of rows. //
    # divides without remainder, so 7 rows give row 3. copy() leaves the rows of the
    # first version unchanged. loc[row, column] writes one cell; read_prices numbers
    # its rows 0, 1, 2 …, so row 3 is the fourth row. iloc[row] reads a value by
    # position, and float() makes the number a plain Python float the addition accepts.
    middle = len(rows) // 2
    changed = rows.copy()
    changed.loc[middle, "close"] = float(rows["close"].iloc[middle]) + 0.01
    assert dataset_version(settings, symbol, changed) != first
