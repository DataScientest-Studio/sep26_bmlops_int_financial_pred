"""Settings read from the environment and the securities file."""

import os
import tomllib
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from sqlalchemy import URL

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
        final_delay: Time after an exchange's close from which a fetched price is final.
    """

    database_url: str = field(repr=False)
    model_dir: Path
    securities: tuple[Security, ...]
    final_delay: timedelta


def load_settings() -> Settings:
    """Read the settings from the environment and the securities file.

    Environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB, MODEL_DIR and FINAL_DELAY_MINUTES. A missing variable raises KeyError.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-007, scope=function)

    Returns:
        The settings of this deployment.
    """
    env = os.environ
    # URL.create escapes characters with a meaning in URLs, such as @ in a password.
    database_url = URL.create(
        "postgresql+psycopg",
        username=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        host=env["POSTGRES_HOST"],
        port=int(env["POSTGRES_PORT"]),
        database=env["POSTGRES_DB"],
    ).render_as_string(hide_password=False)
    with SECURITIES_FILE.open("rb") as file:
        entries = tomllib.load(file)["securities"]
    securities = tuple(Security(e["symbol"], e["exchange"]) for e in entries)
    final_delay = timedelta(minutes=int(env["FINAL_DELAY_MINUTES"]))

    return Settings(database_url, Path(env["MODEL_DIR"]), securities, final_delay)
