"""Settings read from the environment and the securities file."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

SECURITIES_FILE = Path("config/securities.toml")


@dataclass(frozen=True)
class Security:
    """A security the system forecasts.

    Attributes:
        symbol: Ticker as the data source names it, for example "AAPL.US".
        exchange: Market Identifier Code (MIC) of its exchange, for example "XNAS".
    """

    symbol: str
    exchange: str


@dataclass(frozen=True)
class Settings:
    """Operating values of one deployment.

    Attributes:
        database_url: SQLAlchemy URL of the project database.
        model_dir: Folder where trained models are saved.
        securities: The securities the system loads, trains and forecasts.
    """

    database_url: str
    model_dir: Path
    securities: tuple[Security, ...]


def load_settings() -> Settings:
    """Read the settings from the environment and the securities file.

    Environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB and MODEL_DIR. A missing variable raises KeyError.

    @relation(REQ-DAT-001, scope=function)

    Returns:
        The settings of this deployment.
    """
    env = os.environ
    database_url = (
        f"postgresql+psycopg://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}"
        f"@{env['POSTGRES_HOST']}:{env['POSTGRES_PORT']}/{env['POSTGRES_DB']}"
    )
    with SECURITIES_FILE.open("rb") as file:
        entries = tomllib.load(file)["securities"]
    securities = tuple(Security(e["symbol"], e["exchange"]) for e in entries)
    return Settings(database_url, Path(env["MODEL_DIR"]), securities)
