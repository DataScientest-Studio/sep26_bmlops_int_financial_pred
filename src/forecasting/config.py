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
TRAINING_FILE = PROJECT_DIR / "config" / "training.toml"
DRIFT_CHECKS_FILE = PROJECT_DIR / "config" / "drift_checks.toml"
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
# Fewest evaluation days: a model needs at least one day to be scored on. The most
# depends on each security's stored history; training checks it.
FEWEST_EVALUATION_DAYS = 1
# Range of the retraining interval in trading days: 1 retrains a security on every new
# trading day; above 250, about one trading year, a model stays in use too long.
SHORTEST_RETRAINING_INTERVAL = 1
LONGEST_RETRAINING_INTERVAL = 250
# Range of the drift window in trading days: below 20 the test has too few values to
# find drift; above 250, about one trading year, a drift shows too late.
SHORTEST_DRIFT_WINDOW = 20
LONGEST_DRIFT_WINDOW = 250
# Range of the prediction drift check interval in trading days: 1 checks on every new
# trading day; above 60 a drift shows too late.
SHORTEST_PREDICTION_DRIFT_CHECK_INTERVAL = 1
LONGEST_PREDICTION_DRIFT_CHECK_INTERVAL = 60
# Range of the p-value threshold at or below which a check finds drift: below 0.001 the
# test hardly ever finds drift; above 0.1 it often finds drift where there is none.
LOWEST_DRIFT_P_VALUE_THRESHOLD = 0.001
HIGHEST_DRIFT_P_VALUE_THRESHOLD = 0.1


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
        dataset_dir: Folder where DVC keeps the copies of the training datasets.
        dataset_remote: DVC remote where `dataset_version` pushes each copy.
        mlflow_tracking_uri: Address of the MLflow tracking server and model registry.
        code_commit: Git commit the image was built from, or "unknown".
        code_has_uncommitted_changes: Whether tracked files had uncommitted changes when
            the image was built; None when unknown.
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
        evaluation_days: Latest trading days held back from training for evaluation,
            an integer of at least FEWEST_EVALUATION_DAYS.
        retraining_interval_days: Stored trading days from a security's latest training
            to its next scheduled retraining, an integer from
            SHORTEST_RETRAINING_INTERVAL to LONGEST_RETRAINING_INTERVAL.
        drift_window_days: Latest days each drift check compares: stored trading days,
            or days with a scheduled forecast for the prediction drift check; an integer
            from SHORTEST_DRIFT_WINDOW to LONGEST_DRIFT_WINDOW.
        prediction_drift_check_interval_days: Stored trading days from one prediction
            drift check of a security to its next, an integer from
            SHORTEST_PREDICTION_DRIFT_CHECK_INTERVAL to
            LONGEST_PREDICTION_DRIFT_CHECK_INTERVAL.
        drift_p_value_threshold: P-value at or below which a drift check finds drift, a
            decimal number from LOWEST_DRIFT_P_VALUE_THRESHOLD to
            HIGHEST_DRIFT_P_VALUE_THRESHOLD.
    """

    database_url: str = field(repr=False)
    dataset_dir: Path
    dataset_remote: str
    mlflow_tracking_uri: str
    code_commit: str
    code_has_uncommitted_changes: bool | None
    securities: tuple[Security, ...]
    indices: tuple[Security, ...]
    final_delay: timedelta
    daily_update: DailyUpdate
    history_start: date
    replay_database_url: str = field(repr=False)
    replay_start: date
    evaluation_days: int
    retraining_interval_days: int
    drift_window_days: int
    prediction_drift_check_interval_days: int
    drift_p_value_threshold: float

    def exchange_of(self, symbol: str) -> str:
        """Return the exchange of a security; the symbol must be a configured one."""
        # next takes the first item the generator yields: the exchange of the first
        # security with that symbol.
        return next(s.exchange for s in self.securities if s.symbol == symbol)


def _read_whole_number(
    values: dict[str, Any], key: str, lowest: int, highest: int
) -> int:
    """Return a whole number of a config file, refusing one outside its range.

    Args:
        values: The content of the config file.
        key: Name of the number in the file.
        lowest: Smallest accepted number.
        highest: Largest accepted number.

    Returns:
        The number.

    Raises:
        ValueError: If the number is not an integer (a float or a boolean is refused
            too) from lowest to highest.
    """
    value = values[key]
    if type(value) is not int or not lowest <= value <= highest:
        raise ValueError(
            f"{key} must be an integer from {lowest} to {highest}, got {value!r}"
        )

    return value


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
    minutes = _read_whole_number(
        schedule,
        key,
        shortest // timedelta(minutes=1),
        longest // timedelta(minutes=1),
    )

    return timedelta(minutes=minutes)


def _uncommitted_changes(value: str) -> bool | None:
    """Return whether tracked files had uncommitted changes, from the variable's text.

    Args:
        value: The text of CODE_HAS_UNCOMMITTED_CHANGES, empty when unset.

    Returns:
        True for "true", False for "false", None for empty text.

    Raises:
        ValueError: If the text is anything else.
    """
    if value not in ("true", "false", ""):
        raise ValueError(
            f'CODE_HAS_UNCOMMITTED_CHANGES must be "true", "false" or empty, '
            f"got {value!r}"
        )

    return {"true": True, "false": False}.get(value)


def load_settings() -> Settings:
    """Read the settings from the environment and the files in config/.

    Environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB, HISTORY_START, REPLAY_START and MLFLOW_TRACKING_URI (a missing
    variable raises KeyError); CODE_COMMIT (defaults to "unknown");
    CODE_HAS_UNCOMMITTED_CHANGES ("true" or "false"; unset or empty means unknown).

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-003, scope=function)
    @relation(REQ-DAT-007, scope=function)
    @relation(REQ-MOD-004, scope=function)
    @relation(REQ-MOD-006, scope=function)
    @relation(REQ-AUT-005, scope=function)
    @relation(REQ-AUT-007, scope=function)
    @relation(REQ-MON-001, scope=function)
    @relation(REQ-MON-002, scope=function)

    Returns:
        The settings of this deployment.

    Raises:
        ValueError: If HISTORY_START lies before the first day the trading calendar
            knows or after today; if final_delay_minutes is not an integer from
            SHORTEST_FINAL_DELAY to LONGEST_FINAL_DELAY minutes; if load_limit_minutes
            is not an integer from SHORTEST_LOAD_LIMIT to LONGEST_LOAD_LIMIT minutes;
            if start_after plus the final delay reaches the next day; if weekdays of the
            daily update are invalid; if evaluation_days is not an integer of at least
            FEWEST_EVALUATION_DAYS; if retraining_interval_days, drift_window_days or
            prediction_drift_check_interval_days is not an integer within its range; if
            drift_p_value_threshold is not a decimal number within its range; if a
            symbol or exchange of the securities file is not a non-empty text; if
            CODE_HAS_UNCOMMITTED_CHANGES is neither "true", "false" nor empty.
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
    with TRAINING_FILE.open("rb") as file:
        training = tomllib.load(file)
    evaluation_days = training["evaluation_days"]
    if type(evaluation_days) is not int or evaluation_days < FEWEST_EVALUATION_DAYS:
        raise ValueError(
            f"evaluation_days must be an integer of at least {FEWEST_EVALUATION_DAYS},"
            f" got {evaluation_days!r}"
        )
    retraining_interval_days = _read_whole_number(
        training,
        "retraining_interval_days",
        SHORTEST_RETRAINING_INTERVAL,
        LONGEST_RETRAINING_INTERVAL,
    )
    with DRIFT_CHECKS_FILE.open("rb") as file:
        drift_checks = tomllib.load(file)
    drift_window_days = _read_whole_number(
        drift_checks,
        "drift_window_days",
        SHORTEST_DRIFT_WINDOW,
        LONGEST_DRIFT_WINDOW,
    )
    prediction_drift_check_interval_days = _read_whole_number(
        drift_checks,
        "prediction_drift_check_interval_days",
        SHORTEST_PREDICTION_DRIFT_CHECK_INTERVAL,
        LONGEST_PREDICTION_DRIFT_CHECK_INTERVAL,
    )
    drift_p_value_threshold = drift_checks["drift_p_value_threshold"]
    lowest = LOWEST_DRIFT_P_VALUE_THRESHOLD
    highest = HIGHEST_DRIFT_P_VALUE_THRESHOLD
    if (
        type(drift_p_value_threshold) is not float
        or not lowest <= drift_p_value_threshold <= highest
    ):
        raise ValueError(
            f"drift_p_value_threshold must be a decimal number from {lowest} to "
            f"{highest}, got {drift_p_value_threshold!r}"
        )
    history_start = date.fromisoformat(env["HISTORY_START"])
    if not CALENDAR_START <= history_start <= date.today():
        raise ValueError(
            f"HISTORY_START must be from {CALENDAR_START} to today, got {history_start}"
        )

    return Settings(
        database_url=database_url.render_as_string(hide_password=False),
        dataset_dir=DATASET_DIR,
        dataset_remote=DATASET_REMOTE,
        mlflow_tracking_uri=env["MLFLOW_TRACKING_URI"],
        code_commit=env.get("CODE_COMMIT", "unknown"),
        code_has_uncommitted_changes=_uncommitted_changes(
            env.get("CODE_HAS_UNCOMMITTED_CHANGES", "")
        ),
        securities=securities,
        indices=indices,
        final_delay=final_delay,
        daily_update=daily_update,
        history_start=history_start,
        replay_database_url=replay_database_url.render_as_string(hide_password=False),
        replay_start=date.fromisoformat(env["REPLAY_START"]),
        evaluation_days=evaluation_days,
        retraining_interval_days=retraining_interval_days,
        drift_window_days=drift_window_days,
        prediction_drift_check_interval_days=prediction_drift_check_interval_days,
        drift_p_value_threshold=drift_p_value_threshold,
    )
