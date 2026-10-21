"""Replay of stored history into a database of its own, one trading day per run."""

from datetime import date

import pandas as pd
from sqlalchemy import Connection, Engine, text

from forecasting.db import connect, create_database, database_exists

TABLES = ["prices", "splits", "dividends"]
STORED_DAYS = text("SELECT min(day), max(day) FROM prices")
NEXT_DAY = text("SELECT min(day) FROM prices WHERE day > :today")


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
