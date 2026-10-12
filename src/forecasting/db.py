"""Access to the project database."""

import pandas as pd
from sqlalchemy import Engine, create_engine

PRICE_COLUMNS = ["day", "open", "high", "low", "close", "volume", "fetched_at"]


def connect(database_url: str) -> Engine:
    """Create the engine for the project database.

    @relation(REQ-CON-003, scope=function)

    Args:
        database_url: SQLAlchemy URL, as in `Settings.database_url`.

    Returns:
        An engine; connections are opened when used.
    """
    return create_engine(database_url)


def read_prices(engine: Engine, symbol: str) -> pd.DataFrame:
    """Read the stored daily prices of one security, oldest first.

    @relation(REQ-CON-003, scope=function)

    Args:
        engine: Engine of the project database.
        symbol: Ticker of the security.

    Returns:
        One row per trading day with the columns in `PRICE_COLUMNS`.
    """
    raise NotImplementedError
