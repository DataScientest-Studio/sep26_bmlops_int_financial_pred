"""Training of the forecasting model of one security."""

from dataclasses import dataclass
from datetime import date
from typing import Any

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.sklearn import load_model, log_model
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import Engine

from forecasting.config import Settings
from forecasting.datasets import dataset_version
from forecasting.db import connect, database_exists, read_prices
from forecasting.evaluate import Evaluation, evaluate
from forecasting.features import (
    CHANGE_DAYS,
    VOLATILITY_WINDOWS,
    build_features,
    build_target,
)
from forecasting.load import is_final
from forecasting.replay import REPLAY_EXPERIMENT_NAME

# A regression needs about ten training samples for each number it learns, one per
# input plus one for the intercept, before its fit means anything (a common rule of
# thumb in regression). More inputs therefore need more samples.
SAMPLES_PER_INPUT = 10
EXPERIMENT_NAME = "forecasting"


@dataclass(frozen=True)
class TrainingResult:
    """Outcome of a training run.

    Attributes:
        symbol: Ticker of the security.
        model_version: Version of the registered model in MLflow.
        promoted: True if the model became the security's production model.
        training_end: Last day of the training period.
        evaluation_start: First day of the evaluation period, after
            `training_end`.
        evaluation: Scores of the model and both baselines.
    """

    symbol: str
    model_version: str
    promoted: bool
    training_end: date
    evaluation_start: date
    evaluation: Evaluation


def train(engine: Engine, settings: Settings, symbol: str) -> TrainingResult:
    """Train a model on the stored prices of one security and record the run in MLflow.

    The latest days are held back for evaluation; the model is fitted on all earlier
    days, scored against the persistence and mean-change baselines, registered in
    MLflow and promoted to production if it is the security's first model or has a
    lower evaluation error than the current production model on the same days.

    @relation(REQ-DAT-006, scope=function)
    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-MOD-002, scope=function)
    @relation(REQ-MOD-003, scope=function)
    @relation(REQ-MOD-004, scope=function)
    @relation(REQ-MOD-005, scope=function)
    @relation(REQ-SVC-002, scope=function)

    Args:
        engine: Engine of the project database.
        settings: Settings of this deployment.
        symbol: Ticker of the security.

    Returns:
        The model version, whether it was promoted, the periods used and the
        evaluation.
    """
    # Callers pass a configured security: the route refuses any other symbol, the
    # commands loop over the configured ones. is_final needs its exchange to know when
    # that exchange closes.
    exchange = settings.exchange_of(symbol)
    replaying = database_exists(settings.replay_database_url)
    if replaying:
        replay_engine = connect(settings.replay_database_url)
        prices = read_prices(replay_engine, symbol)
        replay_engine.dispose()
    else:
        prices = read_prices(engine, symbol)
    # One True or False per row: is that day's close final? zip walks both columns side
    # by side. prices[final] keeps the True rows, so a provisional close, which may
    # still change, never enters training.
    final = [
        is_final(exchange, day, fetched_at, settings.final_delay)
        for day, fetched_at in zip(prices["day"], prices["fetched_at"])
    ]
    prices = prices[final]
    features = build_features(prices)
    target = build_target(prices)
    # A row is usable when every feature and the target are present: the first rows
    # lack history for the features, the latest row lacks a next day for the target.
    # all(axis=1) checks across the columns of each row.
    usable = features.notna().all(axis=1) & target.notna()
    features = features[usable]
    target = target[usable]
    days = prices["day"][usable]
    # The latest EVALUATION_DAYS rows are held back to score the model; all rows before
    # them train it. The rows are oldest first, so cutting by position keeps every
    # evaluation day later than every training day; shuffling would let later days
    # leak into training. A fixed count rather than a share: a share of a long history
    # would hold back years of the latest days, so the served model would stop learning
    # long ago; a fixed count keeps training close to today whatever the history
    # length, and every model is scored on a window of the same length (REQ-MOD-005).
    split = count_training_samples(
        symbol, len(target), features.shape[1], settings.evaluation_days
    )
    version = dataset_version(settings, symbol, prices)
    training_features = features.iloc[:split]
    training_target = target.iloc[:split]
    evaluation_features = features.iloc[split:]
    evaluation_target = target.iloc[split:]
    # The scaler brings every feature to mean 0 and spread 1 before the regression; it
    # does not change LinearRegression's predictions, but keeps a switch to Ridge, whose
    # penalty depends on the feature scale, a one-word change. The pipeline saves both
    # as one model.
    model = make_pipeline(StandardScaler(), LinearRegression())
    # fit runs the scaler and then the regression on the training rows only: the
    # scaler learns its averages from the training days, so evaluation days never
    # shape them, a second, less obvious kind of no look-ahead.
    model.fit(training_features, training_target)
    # predict returns a plain array; the evaluation days' row labels let evaluate
    # compare each prediction with the actual change of its own day.
    predicted = pd.Series(
        model.predict(evaluation_features), index=evaluation_target.index
    )
    evaluation = evaluate(evaluation_target, predicted, training_target)
    model_name = f"replay-forecast-{symbol}" if replaying else f"forecast-{symbol}"
    experiment_name = REPLAY_EXPERIMENT_NAME if replaying else EXPERIMENT_NAME
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)
    promoted = _beats_production(
        model_name, evaluation_features, evaluation_target, evaluation.model.mae
    )
    with mlflow.start_run():
        mlflow.log_params(
            {
                "symbol": symbol,
                "change_days": CHANGE_DAYS,
                "volatility_windows": str(VOLATILITY_WINDOWS),
                "evaluation_days": settings.evaluation_days,
                "training_samples": split,
                "dataset_version": version,
                "code_version": settings.code_version,
            }
        )
        mlflow.log_metrics(
            {
                "model_mae": evaluation.model.mae,
                "model_skill": evaluation.model.skill,
                "model_directional_accuracy": evaluation.model.directional_accuracy,
                "persistence_mae": evaluation.persistence.mae,
                "persistence_skill": evaluation.persistence.skill,
                "persistence_directional_accuracy": (
                    evaluation.persistence.directional_accuracy
                ),
                "mean_change_mae": evaluation.mean_change.mae,
                "mean_change_skill": evaluation.mean_change.skill,
                "mean_change_directional_accuracy": (
                    evaluation.mean_change.directional_accuracy
                ),
            }
        )
        logged = log_model(model, name="model", registered_model_name=model_name)
    model_version = str(logged.registered_model_version)
    if promoted:
        client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
        client.set_registered_model_alias(model_name, "production", model_version)

    # split - 1 is the last training row, split the first evaluation row.
    return TrainingResult(
        symbol=symbol,
        model_version=model_version,
        promoted=promoted,
        training_end=days.iloc[split - 1],
        evaluation_start=days.iloc[split],
        evaluation=evaluation,
    )


def _beats_production(
    model_name: str,
    evaluation_features: pd.DataFrame,
    evaluation_target: pd.Series,
    candidate_mae: float,
) -> bool:
    """Tell whether the candidate has a lower MAE than the current production model.

    When the security has no production model yet, the candidate becomes the first one.
    """
    try:
        production_model: Any = load_model(f"models:/{model_name}@production")
    except MlflowException as error:
        if error.error_code == "RESOURCE_DOES_NOT_EXIST":
            return True
        raise
    predicted = pd.Series(
        production_model.predict(evaluation_features), index=evaluation_target.index
    )
    production_mae = float((evaluation_target - predicted).abs().mean())

    return bool(candidate_mae < production_mae)


def count_training_samples(
    symbol: str, samples: int, inputs: int, evaluation_days: int
) -> int:
    """Return how many of the oldest samples train the model.

    The latest `evaluation_days` samples are held back to score it. A regression
    needs `SAMPLES_PER_INPUT` training samples for each number it learns, one per
    input plus one for the intercept.

    @relation(REQ-MOD-003, scope=function)

    Args:
        symbol: Ticker of the security, named in the error.
        samples: Usable samples of the security, each with all inputs and a target.
        inputs: Number of model inputs per sample.
        evaluation_days: Latest samples held back for evaluation.

    Returns:
        The number of training samples.

    Raises:
        ValueError: If fewer than `SAMPLES_PER_INPUT * (inputs + 1)` training samples
            would remain.
    """
    training_samples = samples - evaluation_days
    minimum_training_samples = SAMPLES_PER_INPUT * (inputs + 1)
    # A window too large for the stored history would otherwise train on too few
    # samples, or score on fewer days than EVALUATION_DAYS, without any error.
    if training_samples < minimum_training_samples:
        raise ValueError(
            f"{symbol} has {samples} usable samples; EVALUATION_DAYS="
            f"{evaluation_days} leaves {training_samples} for training, fewer than"
            f" {minimum_training_samples}"
        )

    return training_samples
