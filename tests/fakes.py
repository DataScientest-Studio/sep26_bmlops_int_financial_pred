"""Stand-ins for outside systems, so tests need no network."""

import exchange_calendars
import numpy as np
import pandas as pd

from forecasting.config import Security

SECURITIES = (Security("TEST.US", "XNYS"), Security("TEST.DE", "XETR"))


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

    def __init__(self, histories: dict[str, pd.DataFrame]) -> None:
        """Keep the histories to deliver.

        Args:
            histories: Price history per ticker.
        """
        self.histories = histories

    def fetch_history(self, symbol: str) -> pd.DataFrame:
        """Deliver the prepared history of one security.

        Args:
            symbol: Ticker of the security.

        Returns:
            A copy of the prepared history.
        """
        return self.histories[symbol].copy()


def standard_source() -> FakeSource:
    """Deliver about a year of valid prices for each test security."""
    return FakeSource(
        {
            s.symbol: price_history(s.exchange, "2025-01-01", "2025-12-31", seed=i)
            for i, s in enumerate(SECURITIES)
        }
    )
