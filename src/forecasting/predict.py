"""Forecasts of one security, its recent closes and its production model's results."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.entities.model_registry import ModelVersion
from mlflow.exceptions import MlflowException
from mlflow.sklearn import load_model
from sqlalchemy import Engine, text

from forecasting.config import Settings
from forecasting.db import read_prices, read_splits
from forecasting.evaluate import Scores
from forecasting.features import build_features, correct_for_splits
from forecasting.replay import history_database
from forecasting.trading_calendar import next_trading_day
from forecasting.train import (
    MISSING_MODEL_ERRORS,
    PRODUCTION_ALIAS,
    registered_model_name,
)

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


class NoProductionModel(LookupError):
    """A configured security has no production model yet."""


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


@dataclass(frozen=True)
class ProductionResults:
    """The production model of one security and its scores from its training run.

    @relation(REQ-SVC-007, scope=class)

    Attributes:
        symbol: Ticker of the security.
        model_version: Version of the production model in MLflow.
        evaluation_days: Number of evaluation days its training run scored it on.
        model: Scores of the production model on those days.
        persistence: Scores of the persistence baseline on the same days.
        mean_change: Scores of the mean-change baseline on the same days.
        mean_change_forecast: The change the mean-change baseline forecasts for every
            day; None when the training run did not record it.
    """

    symbol: str
    model_version: str
    evaluation_days: int
    model: Scores
    persistence: Scores
    mean_change: Scores
    mean_change_forecast: float | None


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

    Raises:
        NoProductionModel: if the security has no production model yet.
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


def recent_closes(
    engine: Engine, settings: Settings, symbol: str, days: int
) -> pd.DataFrame:
    """Return the closes of a security's latest stored trading days, oldest first.

    The closes are corrected for splits, so a split shows no false drop; the latest
    close may still be provisional.

    @relation(REQ-DAT-003, scope=function)
    @relation(REQ-SVC-006, scope=function)

    Args:
        engine: Engine of the project database; while the replay database exists,
            the closes are read from that instead.
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        days: How many of the latest stored trading days to return.

    Returns:
        One row per trading day with the columns `day` and `close`.
    """
    with history_database(engine, settings) as (database, _):
        prices = read_prices(database, symbol)
        splits = read_splits(database, symbol)
    corrected = correct_for_splits(prices, splits)

    return corrected[["day", "close"]].tail(days)


def production_results(
    engine: Engine, settings: Settings, symbol: str
) -> ProductionResults:
    """Return a security's production model with the scores of its training run.

    @relation(REQ-DAT-003, scope=function)
    @relation(REQ-SVC-007, scope=function)

    Args:
        engine: Engine of the project database; while the replay database exists,
            the replay model is reported instead.
        settings: Settings of this deployment; `mlflow_tracking_uri` names the MLflow
            server.
        symbol: Ticker of the security.

    Returns:
        The model version, its evaluation days, the scores of the model and both
        baselines on them, and the mean-change baseline's forecast, if recorded.

    Raises:
        NoProductionModel: if the security has no production model yet.
        ValueError: if the production model has no training run.
    """
    with history_database(engine, settings) as (_, replaying):
        version = _production_version(settings, symbol, replaying)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    # Training registers every model from a run; a model registered by hand may have
    # none.
    if version.run_id is None:
        raise ValueError(f"The production model of {symbol} has no training run")
    run = client.get_run(version.run_id)
    metrics = run.data.metrics

    return ProductionResults(
        symbol=symbol,
        model_version=str(version.version),
        evaluation_days=int(run.data.params["evaluation_days"]),
        model=_recorded_scores(metrics, "model"),
        persistence=_recorded_scores(metrics, "persistence"),
        mean_change=_recorded_scores(metrics, "mean_change"),
        mean_change_forecast=metrics.get("mean_change_forecast"),
    )


def _recorded_scores(metrics: dict[str, float], forecaster: str) -> Scores:
    """Return the scores a training run recorded for one forecaster."""
    return Scores(
        mae=metrics[f"{forecaster}_mae"],
        skill=metrics[f"{forecaster}_skill"],
        directional_accuracy=metrics[f"{forecaster}_directional_accuracy"],
    )


def _production_version(
    settings: Settings, symbol: str, replaying: bool
) -> ModelVersion:
    """Return the version of a security's production model in MLflow.

    Raises:
        NoProductionModel: if no version of the security's model is in production.
    """
    name = registered_model_name(symbol, replaying)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    # MLflow answers with an error when no model of that name exists yet or none of
    # its versions has the alias production.
    try:
        return client.get_model_version_by_alias(name, PRODUCTION_ALIAS)
    except MlflowException as error:
        if error.error_code in MISSING_MODEL_ERRORS:
            raise NoProductionModel(f"No production model for {symbol} yet") from error
        raise


def _production_model(
    settings: Settings, symbol: str, replaying: bool
) -> tuple[str, Any]:
    """Return the version and the model of a security's production model in MLflow."""
    version = str(_production_version(settings, symbol, replaying).version)
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    name = registered_model_name(symbol, replaying)

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
