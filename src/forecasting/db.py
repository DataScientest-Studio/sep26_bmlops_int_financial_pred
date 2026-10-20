"""Access to the project database and the databases built with its tables."""

from pathlib import Path

import pandas as pd
import psycopg
from psycopg import sql
from sqlalchemy import Engine, create_engine, make_url, text

INIT_DIR = Path("db/init")

PRICE_COLUMNS = ["day", "open", "high", "low", "close", "volume", "fetched_at"]
SPLIT_COLUMNS = ["day", "ratio"]
DIVIDEND_COLUMNS = ["day", "amount", "currency"]

READ_PRICES = text(
    "SELECT day, open, high, low, close, volume, fetched_at FROM prices"
    " WHERE symbol = :symbol ORDER BY day"
)


def connect(database_url: str) -> Engine:
    """Create the engine for a database, such as the project database.

    @relation(REQ-CON-003, scope=function)

    Args:
        database_url: SQLAlchemy URL, as in `Settings.database_url`.

    Returns:
        An engine; connections are opened when used.
    """
    return create_engine(database_url)


def create_database(database_url: str) -> None:
    """Create an empty database with the project's tables from `db/init/`.

    A database of that name is dropped first.

    @relation(REQ-DAT-003, scope=function)

    Args:
        database_url: SQLAlchemy URL of the database to create.
    """
    drop_database(database_url)
    create = sql.SQL("CREATE DATABASE {}")
    with psycopg.connect(_server_url(database_url), autocommit=True) as server:
        server.execute(create.format(_name(database_url)))
    engine = connect(database_url).execution_options(isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        for script in sorted(INIT_DIR.glob("*.sql")):
            connection.exec_driver_sql(script.read_text())
    engine.dispose()


def database_exists(database_url: str) -> bool:
    """Tell whether the server holds the database.

    @relation(REQ-DAT-003, scope=function)

    Args:
        database_url: SQLAlchemy URL of the database.

    Returns:
        True if a database of that name exists.
    """
    name = make_url(database_url).database
    query = "SELECT 1 FROM pg_database WHERE datname = %s"
    with psycopg.connect(_server_url(database_url)) as server:
        found = server.execute(query, (name,)).fetchone()

    return found is not None


def drop_database(database_url: str) -> None:
    """Drop the database and close its connections; a missing one is no error.

    @relation(REQ-DAT-003, scope=function)

    Args:
        database_url: SQLAlchemy URL of the database to drop.
    """
    drop = sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)")
    with psycopg.connect(_server_url(database_url), autocommit=True) as server:
        server.execute(drop.format(_name(database_url)))


def _name(database_url: str) -> sql.Identifier:
    """Return the database name of the URL, quoted for SQL; ValueError if none."""
    name = make_url(database_url).database
    if not name:
        raise ValueError("the database URL names no database")

    return sql.Identifier(name)


def _server_url(database_url: str) -> str:
    """Return the psycopg URL of the server's `postgres` database on the same login."""
    # SQLAlchemy names its driver in the URL (postgresql+psycopg://); psycopg itself
    # takes only the plain postgresql:// form.
    url = make_url(database_url).set(drivername="postgresql", database="postgres")

    return url.render_as_string(hide_password=False)


def read_prices(engine: Engine, symbol: str) -> pd.DataFrame:
    """Read the stored daily prices of one security, oldest first.

    @relation(REQ-CON-003, scope=function)

    Args:
        engine: Engine of the project database.
        symbol: Ticker of the security.

    Returns:
        One row per trading day with the columns in `PRICE_COLUMNS`.
    """
    with engine.connect() as connection:
        prices = pd.read_sql(READ_PRICES, connection, params={"symbol": symbol})
    # PostgreSQL numeric arrives as decimal; the model needs float.
    for column in ["open", "high", "low", "close"]:
        prices[column] = prices[column].astype(float)

    return prices
