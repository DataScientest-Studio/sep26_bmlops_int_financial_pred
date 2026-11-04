"""Settings read from the environment and the files in config/."""

import os
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import URL

from forecasting.trading_calendar import CALENDAR_START

# The project is installed editable, so Python runs this file from the project folder,
# as src/forecasting/config.py; paths found from it do not depend on the folder a
# command starts in.
PROJECT_DIR = Path(__file__).resolve().parents[2]
SECURITIES_FILE = PROJECT_DIR / "config" / "securities.toml"
DAILY_UPDATE_FILE = PROJECT_DIR / "config" / "daily_update.toml"
DATASET_DIR = PROJECT_DIR / "datasets"
DATASET_REMOTE = "s3://datasets"
# Range of the final delay: below 25 minutes a price from before the close can count as
# final (EODHD lags about 15 minutes, and Xetra's closing auction ends about 6 minutes
# after its close); above 60 a day's close stays provisional longer for no gain.
SHORTEST_FINAL_DELAY = timedelta(minutes=25)
LONGEST_FINAL_DELAY = timedelta(minutes=60)
# Range of the load limit: below 20 minutes a slow but healthy load can be cut off;
# above 60 a missed daily update is noticed too late.
SHORTEST_LOAD_LIMIT = timedelta(minutes=20)
LONGEST_LOAD_LIMIT = timedelta(minutes=60)


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
class DailyUpdate:
    """When the daily update pipeline loads the new trading days.

    Attributes:
        weekdays: Days the load runs on, Monday = 1 to Sunday = 7, each once.
        timezone: Time zone of the weekdays and of start_after.
        start_after: Time the load waits for; it starts the final delay later.
        load_limit: Longest a load may run, an integer number of minutes from
            SHORTEST_LOAD_LIMIT to LONGEST_LOAD_LIMIT.
    """

    weekdays: tuple[int, ...]
    timezone: ZoneInfo
    start_after: time
    load_limit: timedelta

    def __post_init__(self) -> None:
        """Refuse invalid weekdays.

        Raises:
            ValueError: If weekdays is empty, holds anything but the integers 1 to 7 or
                holds a day twice.
        """
        days = self.weekdays
        valid = all(type(day) is int and 1 <= day <= 7 for day in days)
        if not days or not valid or len(set(days)) != len(days):
            raise ValueError(f"weekdays must be days 1 to 7, each once, got {days!r}")


@dataclass(frozen=True)
class Settings:
    """Operating values of one deployment.

    Attributes:
        database_url: SQLAlchemy URL of the project database.
        model_dir: Folder where trained models are saved.
        dataset_dir: Folder where DVC keeps the copies of the training datasets.
        dataset_remote: DVC remote where `dataset_version` pushes each copy.
        code_version: Git commit the image was built from, or "unknown".
        securities: The securities the system loads, trains and forecasts.
        indices: Market indices loaded as reference series, never forecasts.
        final_delay: Time after an exchange's close from which a fetched price is final,
            an integer number of minutes from SHORTEST_FINAL_DELAY to
            LONGEST_FINAL_DELAY.
        daily_update: When the daily update pipeline loads the new trading days.
        history_start: First day of price history loaded for a security with none
            stored.
        replay_database_url: SQLAlchemy URL of the database replay copies into, named
            after the project database with `_replay`.
        replay_start: Simulated today of the first replay run.
    """

    database_url: str = field(repr=False)
    model_dir: Path
    dataset_dir: Path
    dataset_remote: str
    code_version: str
    securities: tuple[Security, ...]
    indices: tuple[Security, ...]
    final_delay: timedelta
    daily_update: DailyUpdate
    history_start: date
    replay_database_url: str = field(repr=False)
    replay_start: date


def _minutes(
    schedule: dict[str, Any], key: str, shortest: timedelta, longest: timedelta
) -> timedelta:
    """Return a minute value of the daily update file, refusing one outside its range.

    Args:
        schedule: The content of the daily update file.
        key: Name of the minute value in the file.
        shortest: Smallest accepted value.
        longest: Largest accepted value.

    Returns:
        The value as a duration.

    Raises:
        ValueError: If the value is not an integer (a float or a boolean is refused
            too) from shortest to longest minutes.
    """
    value = schedule[key]
    low = shortest // timedelta(minutes=1)
    high = longest // timedelta(minutes=1)
    if type(value) is not int or not low <= value <= high:
        raise ValueError(
            f"{key} must be an integer from {low} to {high}, got {value!r}"
        )

    return timedelta(minutes=value)


def load_settings() -> Settings:
    """Read the settings from the environment and the files in config/.

    Environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB, MODEL_DIR, HISTORY_START and REPLAY_START (a missing variable raises
    KeyError); CODE_VERSION (defaults to "unknown").

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-003, scope=function)
    @relation(REQ-DAT-007, scope=function)
    @relation(REQ-MOD-004, scope=function)
    @relation(REQ-AUT-005, scope=function)

    Returns:
        The settings of this deployment.

    Raises:
        ValueError: If HISTORY_START lies before the first day the trading calendar
            knows; if final_delay_minutes is not an integer from SHORTEST_FINAL_DELAY
            to LONGEST_FINAL_DELAY minutes; if load_limit_minutes is not an integer
            from SHORTEST_LOAD_LIMIT to LONGEST_LOAD_LIMIT minutes; if start_after plus
            the final delay reaches the next day; if weekdays of the daily update are
            invalid; if a symbol or exchange of the securities file is not a non-empty
            text.
    """
    env = os.environ
    # URL.create escapes characters with a meaning in URLs, such as @ in a password.
    server = URL.create(
        "postgresql+psycopg",
        username=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        host=env["POSTGRES_HOST"],
        port=int(env["POSTGRES_PORT"]),
    )
    database = env["POSTGRES_DB"]
    database_url = server.set(database=database)
    # Named after the project database, never set by hand, so replay and replay-reset
    # can never write to or drop the project database. PostgreSQL keeps only the first
    # 63 bytes of a database name: this holds while POSTGRES_DB has at most 56 bytes.
    replay_database_url = server.set(database=f"{database}_replay")
    with SECURITIES_FILE.open("rb") as file:
        listed = tomllib.load(file)
    securities = tuple(Security(**e) for e in listed["securities"])
    indices = tuple(Security(**e) for e in listed["indices"])
    with DAILY_UPDATE_FILE.open("rb") as file:
        schedule = tomllib.load(file)
    final_delay = _minutes(
        schedule, "final_delay_minutes", SHORTEST_FINAL_DELAY, LONGEST_FINAL_DELAY
    )
    daily_update = DailyUpdate(
        weekdays=tuple(schedule["weekdays"]),
        timezone=ZoneInfo(schedule["timezone"]),
        start_after=time.fromisoformat(schedule["start_after"]),
        load_limit=_minutes(
            schedule, "load_limit_minutes", SHORTEST_LOAD_LIMIT, LONGEST_LOAD_LIMIT
        ),
    )
    start = datetime.combine(date.min, daily_update.start_after)
    if (start + final_delay).date() != start.date():
        raise ValueError(
            f"start_after {daily_update.start_after} plus the final delay of "
            f"{schedule['final_delay_minutes']} minutes must end on the same day"
        )
    history_start = date.fromisoformat(env["HISTORY_START"])
    if history_start < CALENDAR_START:
        raise ValueError(f"HISTORY_START must be {CALENDAR_START} or later")

    return Settings(
        database_url=database_url.render_as_string(hide_password=False),
        model_dir=Path(env["MODEL_DIR"]),
        dataset_dir=DATASET_DIR,
        dataset_remote=DATASET_REMOTE,
        code_version=env.get("CODE_VERSION", "unknown"),
        securities=securities,
        indices=indices,
        final_delay=final_delay,
        daily_update=daily_update,
        history_start=history_start,
        replay_database_url=replay_database_url.render_as_string(hide_password=False),
        replay_start=date.fromisoformat(env["REPLAY_START"]),
    )
