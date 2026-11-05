"""Replay of stored history into a database of its own, one trading day per run.

While the replay database exists, training and forecasts read it and keep their MLflow
runs and models apart; resetting the replay deletes the database and those runs and
models.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
from mlflow import MlflowClient
from sqlalchemy import Connection, Engine, text

from forecasting.config import Settings
from forecasting.db import (
    connect,
    create_database,
    database_exists,
    drop_database,
    read_prices,
    read_splits,
)

TABLES = ["prices", "splits", "dividends"]
STORED_DAYS = text("SELECT min(day), max(day) FROM prices")
NEXT_DAY = text("SELECT min(day) FROM prices WHERE day > :today")
# MLflow names of the replay experiment and models start with this, so they stay apart
# from those of the project database and reset_replay finds them.
REPLAY_PREFIX = "replay-"


def replay_next_day(engine: Engine, replay_url: str, replay_start: date) -> date | None:
    """Copy the next stored day from the project database into the replay database.

    The first run, or a run that finds the replay database missing or without prices,
    creates it and copies every stored day up to `replay_start`. Each later run copies
    the replay database's latest day again, so a quote that has become final since
    replaces the provisional one, and then the first stored day after it. Each run
    copies all or nothing. Prices keep their fetch times; splits and dividends are
    copied as stored. The project database is only read.

    @relation(REQ-DAT-003, scope=function)

    Args:
        engine: Engine of the project database.
        replay_url: SQLAlchemy URL of the replay database.
        replay_start: Simulated today of the first run.

    Returns:
        The replay database's latest day, or None if no day was left to add.

    Raises:
        ValueError: If no prices are stored, or if on the first run `replay_start` lies
            before the first or after the latest stored day.
    """
    with engine.connect() as connection:
        first, latest = connection.execute(STORED_DAYS).one()
    if latest is None:
        raise ValueError("nothing is stored to replay; run make load first")
    replay_engine = connect(replay_url)
    today = None
    if database_exists(replay_url):
        with replay_engine.connect() as connection:
            _, today = connection.execute(STORED_DAYS).one()
    if today is None:
        if not first <= replay_start <= latest:
            raise ValueError(
                f"REPLAY_START must lie between {first} and {latest}, the stored days"
            )
        # Creating the database drops it first, which ends the engine's open connection.
        replay_engine.dispose()
        create_database(replay_url)
        start = date.min
        until = replay_start
    elif today < latest:
        start = today
        with engine.connect() as connection:
            until = connection.execute(NEXT_DAY, {"today": today}).scalar_one()
    else:
        start = today
        until = today
    with engine.connect() as source, replay_engine.begin() as target:
        replayed = _copy(source, target, start, until)
    replay_engine.dispose()

    return None if replayed == today else replayed


def _copy(source: Connection, target: Connection, start: date, until: date) -> date:
    """Replace the target's days from `start` to `until`; return its latest day."""
    for table in TABLES:
        delete = text(f"DELETE FROM {table} WHERE day >= :start")
        target.execute(delete, {"start": start})
        query = text(f"SELECT * FROM {table} WHERE day >= :start AND day <= :until")
        rows = pd.read_sql(query, source, params={"start": start, "until": until})
        rows.to_sql(table, target, if_exists="append", index=False)
    _, latest = target.execute(STORED_DAYS).one()

    return latest


@dataclass(frozen=True)
class History:
    """Stored prices and splits of one security and the database they come from.

    Attributes:
        prices: Daily prices, oldest first.
        splits: Splits, oldest first.
        replaying: True if they come from the replay database.
    """

    prices: pd.DataFrame
    splits: pd.DataFrame
    replaying: bool


def read_history(engine: Engine, settings: Settings, symbol: str) -> History:
    """Read one security's prices and splits, from the replay database while it exists.

    @relation(REQ-DAT-003, scope=function)

    Args:
        engine: Engine of the project database, read when no replay database exists.
        settings: Settings; `replay_database_url` names the replay database.
        symbol: Ticker of the security.

    Returns:
        The prices and splits, and whether they come from the replay database.
    """
    replaying = database_exists(settings.replay_database_url)
    source = connect(settings.replay_database_url) if replaying else engine
    history = History(
        prices=read_prices(source, symbol),
        splits=read_splits(source, symbol),
        replaying=replaying,
    )
    # Only the replay engine was created here; the project engine belongs to the caller.
    if replaying:
        source.dispose()

    return history


def reset_replay(settings: Settings) -> None:
    """Delete the replay database and the replay runs and models in MLflow.

    MLflow removes the registered models at once and only marks the runs and model files
    deleted; `make replay-reset` then removes those for good.

    @relation(REQ-DAT-003, scope=function)

    Args:
        settings: Settings of this deployment.
    """
    drop_database(settings.replay_database_url)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    replay_names = f"name LIKE '{REPLAY_PREFIX}%'"
    # Each search returns only one page of results, and deleted items drop out of the
    # next search, so each loop searches again until none is left.
    while models := client.search_registered_models(filter_string=replay_names):
        for model in models:
            client.delete_registered_model(model.name)
    for experiment in client.search_experiments(filter_string=replay_names):
        ids = [experiment.experiment_id]
        while runs := client.search_runs(ids):
            for run in runs:
                client.delete_run(run.info.run_id)
        # MLflow keeps each model's files apart from its run, under a record of its own.
        while files := client.search_logged_models(ids):
            for model_files in files:
                client.delete_logged_model(model_files.model_id)
