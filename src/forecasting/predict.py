"""Forecast of the next trading day's change of one security."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.sklearn import load_model
from sqlalchemy import Engine, text

from forecasting.config import Settings
from forecasting.db import read_prices, read_splits
from forecasting.features import build_features, correct_for_splits
from forecasting.replay import history_database
from forecasting.trading_calendar import next_trading_day
from forecasting.train import PRODUCTION_ALIAS, registered_model_name

SAVE_FORECAST = text(
    """
    INSERT INTO predictions (
        symbol, day, change, model_version, start_close, start_fetched_at,
        change_1, change_2, change_3, change_4, change_5, requested_at
    )
    VALUES (
        :symbol, :day, :change, :model_version, :start_close, :start_fetched_at,
        :change_1, :change_2, :change_3, :change_4, :change_5, :requested_at
    )
    """
)


@dataclass(frozen=True)
class Forecast:
    """A forecast for one security.

    @relation(REQ-SVC-001, scope=class)

    Attributes:
        symbol: Ticker of the security.
        day: The trading day the forecast is for.
        change: Predicted relative close-to-close change to `day`.
        model_version: Version of the production model in MLflow that produced it.
        start_close: The stored close the change starts from: the latest day's close,
            which may still be provisional.
        start_fetched_at: When that close was fetched; it is final if fetched at or
            after its exchange's close that day plus the set delay.
    """

    symbol: str
    day: date
    change: float
    model_version: str
    start_close: float
    start_fetched_at: datetime


def predict(engine: Engine, settings: Settings, symbol: str) -> Forecast:
    """Forecast the change from the latest stored day to the next trading day.

    Each forecast is stored in the database its prices are read from; if storing fails,
    the forecast fails.

    @relation(REQ-DAT-003, scope=function)
    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-SVC-001, scope=function)
    @relation(REQ-SVC-003, scope=function)

    Args:
        engine: Engine of the project database; while the replay database exists,
            the forecast reads that instead and is stored there.
        settings: Settings of this deployment; `mlflow_tracking_uri` names the MLflow
            server.
        symbol: Ticker of the security.

    Returns:
        The forecast with the version of the production model that produced it, and
        the close it starts from with the time that close was fetched.
    """
    requested_at = datetime.now(UTC)
    with history_database(engine, settings) as (database, replaying):
        version, model = _production_model(settings, symbol, replaying)

        prices = read_prices(database, symbol)
        # The model is a formula over the features, so it needs the latest stored
        # day's values of them, computed exactly as in training: from closes corrected
        # for splits. The double brackets keep the latest row as a one-row table, the
        # shape predict expects.
        corrected = correct_for_splits(prices, read_splits(database, symbol))
        features = build_features(corrected).iloc[[-1]]

        # The latest stored day; the forecast starts from its close as stored, which may
        # still be provisional. The next trading day skips weekends and holidays, so a
        # Friday close forecasts Monday. predict returns one value per row; [0] takes
        # the only one, float turns numpy's number into a plain Python float.
        latest = prices.iloc[-1]
        forecast = Forecast(
            symbol=symbol,
            day=next_trading_day(settings.exchange_of(symbol), latest["day"]),
            change=float(model.predict(features)[0]),
            model_version=version,
            start_close=float(latest["close"]),
            start_fetched_at=latest["fetched_at"],
        )

        _save_forecast(database, forecast, features, requested_at)

    return forecast


def _production_model(
    settings: Settings, symbol: str, replaying: bool
) -> tuple[str, Any]:
    """Return the version and the model of a security's production model in MLflow."""
    name = registered_model_name(symbol, replaying)
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    version = str(client.get_model_version_by_alias(name, PRODUCTION_ALIAS).version)

    return version, load_model(f"models:/{name}/{version}")


def _save_forecast(
    database: Engine, forecast: Forecast, features: pd.DataFrame, requested_at: datetime
) -> None:
    """Store a forecast with its input features and the time it was requested."""
    # One row: the forecast's fields, its features by column name (change_1, ...) and
    # the time of the request. str() turns pandas' column names into the text keys the
    # query expects.
    feature_values = {str(name): value for name, value in features.iloc[0].items()}
    row = vars(forecast) | feature_values | {"requested_at": requested_at}
    with database.begin() as connection:
        connection.execute(SAVE_FORECAST, row)
