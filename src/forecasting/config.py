"""Settings read from the environment and the securities file."""

import os
import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import URL

from forecasting.trading_calendar import CALENDAR_START

SECURITIES_FILE = Path("config/securities.toml")


@dataclass(frozen=True)
class Security:
    """A stock or market index the system loads.

    Attributes:
        symbol: Ticker as the data source names it, for example "AAPL.US".
        exchange: Market Identifier Code (MIC) of its exchange, for example "XNAS".
    """

    symbol: str
    exchange: str

    def __post_init__(self) -> None:
        """Refuse a symbol or exchange that is not a non-empty text.

        Raises:
            ValueError: If one of them is empty or not a string.
        """
        for name, value in (("symbol", self.symbol), ("exchange", self.exchange)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty text, got {value!r}")


@dataclass(frozen=True)
class Settings:
    """Operating values of one deployment.

    Attributes:
        database_url: SQLAlchemy URL of the project database.
        model_dir: Folder where trained models are saved.
        securities: The securities the system loads, trains and forecasts.
        indices: Market indices loaded as reference series, never forecasts.
        final_delay: Time after an exchange's close from which a fetched price is final.
        history_start: First day of price history loaded for a security with none
            stored.
    """

    database_url: str = field(repr=False)
    model_dir: Path
    securities: tuple[Security, ...]
    indices: tuple[Security, ...]
    final_delay: timedelta
    history_start: date


def load_settings() -> Settings:
    """Read the settings from the environment and the securities file.

    Environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB, MODEL_DIR, FINAL_DELAY_MINUTES and HISTORY_START. A missing variable
    raises KeyError.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-007, scope=function)

    Returns:
        The settings of this deployment.

    Raises:
        ValueError: If HISTORY_START lies before the first day the trading calendar
            knows.
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
        listed = tomllib.load(file)
    securities = tuple(Security(**e) for e in listed["securities"])
    indices = tuple(Security(**e) for e in listed["indices"])
    final_delay = timedelta(minutes=int(env["FINAL_DELAY_MINUTES"]))
    history_start = date.fromisoformat(env["HISTORY_START"])
    if history_start < CALENDAR_START:
        raise ValueError(f"HISTORY_START must be {CALENDAR_START} or later")

    return Settings(
        database_url=database_url,
        model_dir=Path(env["MODEL_DIR"]),
        securities=securities,
        indices=indices,
        final_delay=final_delay,
        history_start=history_start,
    )
