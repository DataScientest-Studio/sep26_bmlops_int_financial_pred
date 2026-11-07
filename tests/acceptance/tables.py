"""Acceptance-test helpers that fill the database, read its tables and MLflow runs."""

import pandas as pd
from mlflow import MlflowClient
from mlflow.entities import Run
from sqlalchemy import Engine, text

from forecasting.config import Settings
from forecasting.load import load_history
from tests.fakes import INDICES, SECURITIES, source_around


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
