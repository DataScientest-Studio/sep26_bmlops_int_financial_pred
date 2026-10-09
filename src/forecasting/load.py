"""Loading of daily prices from a data source into the database."""

from dataclasses import dataclass
from typing import Protocol

import pandas as pd
from sqlalchemy import Engine

from forecasting.config import Security


class PriceSource(Protocol):
    """A data source of daily prices."""

    def fetch_history(self, symbol: str) -> pd.DataFrame:
        """Fetch the complete daily price history of one security.

        Args:
            symbol: Ticker of the security.

        Returns:
            One row per day with the columns in `forecasting.db.PRICE_COLUMNS`,
            as delivered: rows may be invalid.
        """


@dataclass(frozen=True)
class LoadReport:
    """Outcome of a load.

    Attributes:
        stored: Number of quotes written to the database.
        rejected: Number of quotes refused by validation.
    """

    stored: int
    rejected: int


def load_history(
    engine: Engine, source: PriceSource, securities: tuple[Security, ...]
) -> LoadReport:
    """Load the complete price history of each security in one run.

    A quote already stored for the same security and day is kept, so a
    repeated run adds no duplicates.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-005, scope=function)

    Args:
        engine: Engine of the project database.
        source: Where the prices come from.
        securities: The securities to load.

    Returns:
        How many quotes were stored and how many were rejected.
    """
    raise NotImplementedError
