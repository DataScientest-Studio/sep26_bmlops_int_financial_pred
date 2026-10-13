"""Stand-ins for outside systems, so tests need no network."""

from datetime import datetime

import exchange_calendars
import numpy as np
import pandas as pd

from forecasting.config import Security
from forecasting.db import DIVIDEND_COLUMNS, SPLIT_COLUMNS

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
    days = exchange_calendars.get_calendar(exchange).sessions_in_range(start, end)
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days))))
    return pd.DataFrame(
        {
            "day": days.date,
            "open": close * (1 + rng.normal(0, 0.002, len(days))),
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": rng.integers(1_000, 10_000, len(days)),
        }
    )


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

    def fetch_history(self, symbol: str) -> pd.DataFrame:
        """Deliver the prepared history of one security.

        Args:
            symbol: Ticker of the security.

        Returns:
            A copy of the prepared history, each row stamped with `fetched_at`.
        """
        history = self.histories[symbol].copy()
        history["fetched_at"] = self.fetched_at

        return history

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
