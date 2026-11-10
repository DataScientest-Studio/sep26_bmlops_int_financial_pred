"""Acceptance-test helpers that fill the database, read its tables and MLflow runs."""

from collections.abc import Sequence
from datetime import date

import pandas as pd
from fastapi.testclient import TestClient
from mlflow import MlflowClient
from mlflow.entities import Run
from mlflow.entities.model_registry import ModelVersion
from sqlalchemy import Engine, text

from forecasting.config import Settings
from forecasting.load import load_history
from tests.fakes import (
    CALM,
    INDICES,
    SECURITIES,
    FakeSource,
    history_after,
    history_from_changes,
    source_around,
)

SECURITY = SECURITIES[0]


def stored_table(engine: Engine, table: str) -> pd.DataFrame:
    """Read every stored row of one table straight from it, by symbol and day."""
    query = text(f"SELECT * FROM {table} ORDER BY symbol, day")
    with engine.connect() as connection:
        return pd.read_sql(query, connection)


def run_of(settings: Settings, symbol: str, model_version: str) -> Run:
    """Read the MLflow run that produced one version of a security's model."""
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    version = client.get_model_version(f"forecast-{symbol}", model_version)
    assert version.run_id is not None

    return client.get_run(version.run_id)


def drift_checks(settings: Settings, symbol: str) -> list[Run]:
    """Read the MLflow runs of a security's drift checks, straight from MLflow."""
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    experiment = client.get_experiment_by_name("drift-checks")
    assert experiment is not None

    return client.search_runs(
        [experiment.experiment_id], filter_string=f"tags.symbol = '{symbol}'"
    )


def model_versions(settings: Settings, symbol: str) -> list[ModelVersion]:
    """Read the registered versions of a security's model, straight from MLflow."""
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)

    return list(client.search_model_versions(f"name = 'forecast-{symbol}'"))


def load_history_around_start(engine: Engine, settings: Settings) -> pd.Series:
    """Load the test history around `REPLAY_START`; return the stored days."""
    load_history(
        engine,
        source_around(settings.replay_start),
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )

    return stored_table(engine, "prices")["day"]


def store(engine: Engine, settings: Settings, history: pd.DataFrame) -> None:
    """Store the days of one history for the first test security."""
    source = FakeSource({SECURITY.symbol: history})
    load_history(
        engine, source, (SECURITY,), (), settings.final_delay, settings.history_start
    )


def store_first_year(engine: Engine, settings: Settings) -> date:
    """Store a calm year for the first test security; return its last day."""
    history = history_from_changes(SECURITY.exchange, "2024-01-01", "2024-12-31", CALM)
    store(engine, settings, history)

    return history["day"].iloc[-1]


def store_days_after(
    engine: Engine,
    settings: Settings,
    last_day: date,
    count: int,
    changes: Sequence[float],
) -> date:
    """Store `count` days after `last_day`; return the last of them."""
    history = history_after(SECURITY.exchange, last_day, count, changes)
    store(engine, settings, history)

    return history["day"].iloc[-1]


def store_and_forecast_days(
    client: TestClient, engine: Engine, settings: Settings, history: pd.DataFrame
) -> date:
    """Store each day of `history`, forecast it as scheduled; return the last day."""
    for day in history["day"]:
        store(engine, settings, history[history["day"] == day])
        client.post("/predict", json={"symbol": SECURITY.symbol, "scheduled": True})

    return history["day"].iloc[-1]
