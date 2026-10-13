"""Loading of daily prices from a data source into the database."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

import pandas as pd
from sqlalchemy import Connection, Engine, TextClause, text

from forecasting.config import Security
from forecasting.db import DIVIDEND_COLUMNS, PRICE_COLUMNS, SPLIT_COLUMNS
from forecasting.trading_calendar import is_trading_day, session_close, trading_days

SAVE_QUOTE = text(
    """
    INSERT INTO prices (symbol, day, open, high, low, close, volume, fetched_at)
    VALUES (:symbol, :day, :open, :high, :low, :close, :volume, :fetched_at)
    ON CONFLICT (symbol, day) DO UPDATE SET
        open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
        close = EXCLUDED.close, volume = EXCLUDED.volume,
        fetched_at = EXCLUDED.fetched_at
    WHERE prices.fetched_at < :final_from AND prices.fetched_at < EXCLUDED.fetched_at
    """
)

SAVE_SPLIT = text(
    """
    INSERT INTO splits (symbol, day, ratio) VALUES (:symbol, :day, :ratio)
    ON CONFLICT (symbol, day) DO UPDATE SET ratio = EXCLUDED.ratio
    """
)

SAVE_DIVIDEND = text(
    """
    INSERT INTO dividends (symbol, day, amount, currency)
    VALUES (:symbol, :day, :amount, :currency)
    ON CONFLICT (symbol, day) DO UPDATE SET
        amount = EXCLUDED.amount, currency = EXCLUDED.currency
    """
)


class PriceSource(Protocol):
    """A data source of daily prices, splits and dividends."""

    def fetch_history(self, symbol: str, start: date) -> pd.DataFrame:
        """Fetch the daily price history of one security from a first day on.

        Args:
            symbol: Ticker of the security.
            start: First day to deliver; the source may hold no earlier days anyway.

        Returns:
            One row per day with the columns in `forecasting.db.PRICE_COLUMNS`, as
            delivered: rows may be invalid. `day` holds plain `datetime.date` values,
            never a `datetime` or `pandas.Timestamp`; `fetched_at` holds the time of
            the fetch, timezone-aware.
        """
        ...

    def fetch_splits(self, symbol: str) -> pd.DataFrame:
        """Fetch all splits of one security.

        Args:
            symbol: Ticker of the security.

        Returns:
            One row per split with the columns in `forecasting.db.SPLIT_COLUMNS`:
            `day` as plain `datetime.date`, never a `datetime` or `pandas.Timestamp`;
            `ratio` as new shares per old share (4.0 for a 4-for-1 split). The list
            may hold a split announced for a later day.
        """
        ...

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """Fetch all dividends of one security.

        Args:
            symbol: Ticker of the security.

        Returns:
            One row per dividend with the columns in `forecasting.db.DIVIDEND_COLUMNS`:
            `day` as plain `datetime.date`, never a `datetime` or `pandas.Timestamp`;
            `amount` as paid per share, `currency` as its code (`USD`).
        """
        ...


@dataclass(frozen=True)
class LoadReport:
    """Outcome of a load.

    Attributes:
        stored: Number of quotes of new days written to the database.
        replaced: Number of provisional quotes overwritten by a later fetch.
        rejected: Number of quotes, splits and dividends refused by validation.
        missing: Number of trading days for which the source delivered no quote.
    """

    stored: int
    replaced: int
    rejected: int
    missing: int


def is_final(
    exchange: str, day: date, fetched_at: datetime, final_delay: timedelta
) -> bool:
    """Tell whether a quote's close is final or still provisional.

    @relation(REQ-DAT-007, scope=function)

    Args:
        exchange: MIC of the exchange the security trades on.
        day: Trading day of the quote.
        fetched_at: Time the quote was fetched, timezone-aware.
        final_delay: Time after the exchange's close from which a quote is final.

    Returns:
        True if the quote was fetched at or after the close plus the delay.
    """
    return fetched_at >= _final_from(exchange, day, final_delay)


def _final_from(exchange: str, day: date, final_delay: timedelta) -> datetime:
    """Return the moment from which a fetched quote of that day is final.

    Args:
        exchange: MIC of the exchange the security trades on.
        day: Trading day of the quote.
        final_delay: Time after the exchange's close from which a quote is final.

    Returns:
        The exchange's close that day plus the delay, in UTC.
    """
    return session_close(exchange, day) + final_delay


def _valid_rows(
    delivery: pd.DataFrame, columns: list[str], positive: list[str]
) -> pd.DataFrame:
    """Keep the rows that pass validation.

    A row is refused if a field is missing, a value that must be positive is zero or
    below, or its day was already delivered earlier in the same delivery.

    Args:
        delivery: Rows of one security, as the source delivered them.
        columns: The fields every row must have.
        positive: The fields that must be above zero.

    Returns:
        The valid rows, in delivered order.
    """
    # Each line gives one True/False value per row. True where no field is empty:
    complete = delivery[columns].notna().all(axis="columns")
    # True where all those values are above zero; an empty value compares as False:
    above_zero = (delivery[positive] > 0).all(axis="columns")
    # duplicated() marks the second and later rows of a day; ~ turns that around:
    first_of_day = ~delivery["day"].duplicated()

    return delivery[complete & above_zero & first_of_day]


def _valid_quotes(delivery: pd.DataFrame, exchange: str) -> pd.DataFrame:
    """Keep the quotes that pass validation.

    Beyond the rules of `_valid_rows` a quote is refused if its volume is negative
    or its day is not a trading day of the exchange.

    Args:
        delivery: Quotes of one security, as the source delivered them.
        exchange: MIC of the exchange the security trades on.

    Returns:
        The valid quotes, in delivered order.
    """
    valid = _valid_rows(delivery, PRICE_COLUMNS, ["open", "high", "low", "close"])
    # True where the volume is zero or above:
    traded = valid["volume"] >= 0
    # True where the exchange trades that day; a Series on the same index lets &
    # line the values up row by row:
    trading = [is_trading_day(exchange, day) for day in valid["day"]]
    on_trading_day = pd.Series(trading, index=valid.index, dtype=bool)

    return valid[traded & on_trading_day]


def _traded_volumes(
    quotes: pd.DataFrame, splits: pd.DataFrame, delivered: set[date]
) -> pd.DataFrame:
    """Undo the source's correction of volumes for later splits.

    The source multiplies each volume by the ratio of every later split once a day on
    or after that split's day is delivered, valid or not: a split announced for a day
    after the last delivered day is already listed, yet no volume holds it. This
    divides the applied splits back out and rounds to whole shares.

    Args:
        quotes: Valid quotes of one security.
        splits: Valid splits of the same security.
        delivered: The days the source delivered for that security, valid or not.

    Returns:
        The quotes with volumes as traded on their day.
    """
    divisor = pd.Series(1.0, index=quotes.index)
    for split in splits.to_dict("records"):
        # True when a day on or after the split's was delivered, so it is applied:
        if any(day >= split["day"] for day in delivered):
            divisor.loc[quotes["day"] < split["day"]] *= split["ratio"]
    volume = (quotes["volume"] / divisor).round().astype("int64")

    return quotes.assign(volume=volume)


def _missing_days(delivered: set[date], exchange: str) -> int:
    """Count the trading days for which the source delivered no quote.

    Only days between the first and the last delivered day count; weekends and
    holidays of the exchange are not trading days. A delivered but invalid quote whose
    day is known is rejected, not missing.

    Args:
        delivered: The days the source delivered for one security, valid or not.
        exchange: MIC of the exchange the security trades on.

    Returns:
        The number of trading days in that range without a delivered quote.
    """
    if not delivered:
        return 0

    expected = trading_days(exchange, min(delivered), max(delivered))

    return len(set(expected) - delivered)


def _stored_fetch_times(connection: Connection, symbol: str) -> dict[date, datetime]:
    """Read when each stored quote of one security was fetched.

    Args:
        connection: Open connection to the project database.
        symbol: Ticker of the security.

    Returns:
        The fetch time per stored day.
    """
    query = text("SELECT day, fetched_at FROM prices WHERE symbol = :symbol")
    result = connection.execute(query, {"symbol": symbol})

    return {day: fetched_at for day, fetched_at in result}


def _save_events(
    connection: Connection, statement: TextClause, symbol: str, events: pd.DataFrame
) -> None:
    """Write the splits or dividends of one security; a stored one is replaced."""
    rows = [{**event, "symbol": symbol} for event in events.to_dict("records")]
    if rows:
        connection.execute(statement, rows)


def load_history(
    engine: Engine,
    source: PriceSource,
    securities: tuple[Security, ...],
    indices: tuple[Security, ...],
    final_delay: timedelta,
    history_start: date,
) -> LoadReport:
    """Load the prices of each security and index and each security's events in one run.

    Splits and dividends are fetched for securities only; a market index has none.
    Volumes are stored as traded: the source's correction for later splits is undone.

    Each security's prices are asked for from its latest stored day on, or from
    `history_start` while none is stored; the latest stored day comes again, so a
    provisional close gets its final value. A day not yet stored is added. A stored
    quote that is still provisional is replaced by a later fetch; a final quote is
    kept. So a repeated run adds no duplicates and never changes a final close.

    Trading days without a delivered quote are counted as missing; they do not stop the
    load.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)
    @relation(REQ-DAT-004, scope=function)
    @relation(REQ-DAT-005, scope=function)
    @relation(REQ-DAT-007, scope=function)

    Args:
        engine: Engine of the project database.
        source: Where the prices, splits and dividends come from.
        securities: The securities to load.
        indices: The market indices to load.
        final_delay: Time after the exchange's close from which a quote is final.
        history_start: First day of history asked for while a security has none
            stored.

    Returns:
        How many quotes were stored and replaced, how many quotes and events were
        rejected, and how many trading days had no delivered quote.
    """
    stored = replaced = rejected = missing = 0
    valid_splits: dict[str, pd.DataFrame] = {}
    no_splits = pd.DataFrame(columns=SPLIT_COLUMNS)
    with engine.begin() as connection:
        splits = {s.symbol: source.fetch_splits(s.symbol) for s in securities}
        dividends = {s.symbol: source.fetch_dividends(s.symbol) for s in securities}
        for symbol, delivery in splits.items():
            valid = _valid_rows(delivery, SPLIT_COLUMNS, ["ratio"])
            rejected += len(delivery) - len(valid)
            valid_splits[symbol] = valid
            _save_events(connection, SAVE_SPLIT, symbol, valid)
        for symbol, delivery in dividends.items():
            valid = _valid_rows(delivery, DIVIDEND_COLUMNS, ["amount"])
            rejected += len(delivery) - len(valid)
            _save_events(connection, SAVE_DIVIDEND, symbol, valid)
        for security in (*securities, *indices):
            fetched = _stored_fetch_times(connection, security.symbol)
            start = max(fetched, default=history_start)
            delivery = source.fetch_history(security.symbol, start)
            valid = _valid_quotes(delivery, security.exchange)
            rejected += len(delivery) - len(valid)
            # A row without a day belongs to no day; it is only rejected:
            delivered = set(delivery["day"].dropna())
            missing += _missing_days(delivered, security.exchange)
            # Store volumes as traded, so a later split never makes a stored quote
            # wrong; indices have no splits and keep their volumes:
            splits_of_security = valid_splits.get(security.symbol, no_splits)
            valid = _traded_volumes(valid, splits_of_security, delivered)
            to_save = []
            for quote in valid[PRICE_COLUMNS].to_dict("records"):
                day = quote["day"]
                if day not in fetched:
                    stored += 1
                elif quote["fetched_at"] > fetched[day] and not is_final(
                    security.exchange, day, fetched[day], final_delay
                ):
                    replaced += 1
                else:
                    continue
                # The database itself replaces only a provisional quote and only with
                # a later fetch; final_from tells it from when a quote is final.
                final_from = _final_from(security.exchange, day, final_delay)
                row = {**quote, "symbol": security.symbol, "final_from": final_from}
                to_save.append(row)
            if to_save:
                connection.execute(SAVE_QUOTE, to_save)

    return LoadReport(stored, replaced, rejected, missing)
