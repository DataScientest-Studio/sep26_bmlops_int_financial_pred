"""Stand-ins for outside systems, so tests need no network."""

from collections.abc import Sequence
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from forecasting.config import Security
from forecasting.db import DIVIDEND_COLUMNS, SPLIT_COLUMNS
from forecasting.load import Delivery
from forecasting.trading_calendar import next_trading_day, trading_days

SECURITIES = (Security("TEST.US", "XNYS"), Security("TEST.DE", "XETR"))
INDICES = (Security("TEST.INDX", "XNYS"),)
FETCHED_AT = datetime.fromisoformat("2026-01-02T12:00:00+00:00")


def price_history(exchange: str, start: str, end: str, seed: int) -> pd.DataFrame:
    """Build a random-walk price history on the exchange's real trading days.

    Args:
        exchange: MIC of the exchange.
        start: First calendar date, ISO format.
        end: Last calendar date, ISO format.
        seed: Seed of the random walk, so tests repeat exactly.

    Returns:
        One row per trading day with the price columns of the database.
    """
    days = trading_days(exchange, date.fromisoformat(start), date.fromisoformat(end))
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))

    return pd.DataFrame(
        {
            "day": days,
            "open": close * (1 + rng.normal(0, 0.002, len(days))),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": rng.integers(1_000, 10_000, len(days)),
        }
    )


def _prices_on(days: list[date], changes: Sequence[float]) -> pd.DataFrame:
    """Build prices from 100 whose close-to-close changes cycle through `changes`."""
    steps = [1.0] + [1 + changes[i % len(changes)] for i in range(len(days) - 1)]
    close = 100 * np.cumprod(steps)

    return pd.DataFrame(
        {
            "day": days,
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1_000,
        }
    )


def history_from_changes(
    exchange: str, start: str, end: str, changes: Sequence[float]
) -> pd.DataFrame:
    """Build a price history whose daily changes are exactly the given ones.

    Args:
        exchange: MIC of the exchange.
        start: First calendar date, ISO format.
        end: Last calendar date, ISO format.
        changes: Relative close-to-close changes, each above -1; the changes from one
            day to the next cycle through them, starting with the first.

    Returns:
        One row per trading day with the price columns of the database; the first
        close is 100.
    """
    days = trading_days(exchange, date.fromisoformat(start), date.fromisoformat(end))

    return _prices_on(days, changes)


def history_after(
    exchange: str, last_day: date, count: int, changes: Sequence[float]
) -> pd.DataFrame:
    """Build the prices of the trading days after a day, like `history_from_changes`.

    Args:
        exchange: MIC of the exchange.
        last_day: The day before the first day built; need not be a trading day.
        count: Number of trading days to build.
        changes: Relative close-to-close changes, as for `history_from_changes`.

    Returns:
        `count` rows; the first close is 100, whatever the closes before were.
    """
    first = next_trading_day(exchange, last_day)
    # Two calendar days for each trading day, plus a margin for holidays, always hold
    # `count` trading days.
    ahead = first + timedelta(days=2 * count + 10)
    days = trading_days(exchange, first, ahead)[:count]

    return _prices_on(days, changes)


class FakeSource:
    """A data source that delivers prepared price histories."""

    def __init__(
        self,
        histories: dict[str, pd.DataFrame],
        fetched_at: datetime = FETCHED_AT,
        splits: dict[str, pd.DataFrame] | None = None,
        dividends: dict[str, pd.DataFrame] | None = None,
    ) -> None:
        """Keep the histories and events to deliver and the fetch time to stamp on them.

        Args:
            histories: Price history per ticker.
            fetched_at: Time the fetch takes place (UTC); tests move it between loads.
            splits: Splits per ticker; a ticker without an entry has none.
            dividends: Dividends per ticker; a ticker without an entry has none.
        """
        self.histories = histories
        self.fetched_at = fetched_at
        self.splits = splits or {}
        self.dividends = dividends or {}
        self.starts: dict[str, date] = {}

    def fetch_history(self, symbol: str, start: date) -> Delivery:
        """Deliver the prepared history of one security from `start` on.

        Each call records its start in `starts`, so tests see what was asked for.

        Args:
            symbol: Ticker of the security.
            start: First day to deliver.

        Returns:
            `fetched_at` and a copy of the prepared days from `start` on, each stamped
            with `fetched_at`.
        """
        self.starts[symbol] = start
        history = self.histories[symbol]
        delivered = history[history["day"] >= start].copy()
        delivered["fetched_at"] = self.fetched_at

        return Delivery(self.fetched_at, delivered)

    def fetch_splits(self, symbol: str) -> pd.DataFrame:
        """Deliver the prepared splits of one security.

        Args:
            symbol: Ticker of the security.

        Returns:
            A copy of the prepared splits, empty if there are none.
        """
        return self.splits.get(symbol, pd.DataFrame(columns=SPLIT_COLUMNS)).copy()

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """Deliver the prepared dividends of one security.

        Args:
            symbol: Ticker of the security.

        Returns:
            A copy of the prepared dividends, empty if there are none.
        """
        return self.dividends.get(symbol, pd.DataFrame(columns=DIVIDEND_COLUMNS)).copy()


def standard_source(
    splits: dict[str, pd.DataFrame] | None = None,
    dividends: dict[str, pd.DataFrame] | None = None,
) -> FakeSource:
    """Deliver about a year of valid prices for each test security and index."""
    return FakeSource(
        {
            s.symbol: price_history(s.exchange, "2025-01-01", "2025-12-31", seed=i)
            for i, s in enumerate(SECURITIES + INDICES)
        },
        splits=splits,
        dividends=dividends,
    )


def source_around(day: date) -> FakeSource:
    """Deliver two months of prices, a split and a dividend on both sides of `day`."""
    start = (day - timedelta(days=30)).isoformat()
    end = (day + timedelta(days=30)).isoformat()
    before = day - timedelta(days=10)
    after = day + timedelta(days=10)

    return FakeSource(
        {
            s.symbol: price_history(s.exchange, start, end, seed=i)
            for i, s in enumerate(SECURITIES + INDICES)
        },
        splits={"TEST.US": pd.DataFrame({"day": [before, after], "ratio": [2.0, 3.0]})},
        dividends={
            "TEST.US": pd.DataFrame(
                {"day": [before, after], "amount": [0.25, 0.30], "currency": "USD"}
            )
        },
    )
