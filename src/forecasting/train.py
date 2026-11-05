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
from forecasting.db import read_prices, read_splits
from forecasting.evaluate import Evaluation, evaluate
from forecasting.features import (
    CHANGE_DAYS,
    build_features,
    build_target,
    correct_for_splits,
)
from forecasting.load import is_final

# A regression needs about ten training samples for each number it learns, one per
# input plus one for the intercept, before its fit means anything (a common rule of
# thumb in regression). More inputs therefore need more samples.
SAMPLES_PER_INPUT = 10
EXPERIMENT_NAME = "forecasting"
PRODUCTION_ALIAS = "production"


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


def registered_model_name(symbol: str) -> str:
    """Return the name a security's models are registered under in MLflow."""
    return f"forecast-{symbol}"


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
    stored = read_prices(engine, symbol)
    # One True or False per row: is that day's close final? zip walks both columns side
    # by side. stored.loc[final] keeps the True rows, so a provisional close, which may
    # still change, never enters training.
    final = [
        is_final(exchange, day, fetched_at, settings.final_delay)
        for day, fetched_at in zip(stored["day"], stored["fetched_at"])
    ]
    # correct_for_splits expresses the final days in the shares of the latest final
    # day; a split after that day has not happened for these rows yet.
    prices = correct_for_splits(stored.loc[final], read_splits(engine, symbol))
    features = build_features(prices)
    target = build_target(prices)
    # A row is usable when every feature and the target are present: the first rows
    # lack history for the features, the latest row lacks a next day for the target.
    # all(axis=1) checks across the columns of each row.
    usable = features.notna().all(axis=1) & target.notna()
    features = features[usable]
    target = target[usable]
    days = prices["day"][usable]
    # The latest evaluation_days rows are held back to score the model; all rows before
    # them train it. The rows are oldest first, so cutting by position keeps every
    # evaluation day later than every training day; shuffling would let later days
    # leak into training. A fixed count rather than a share: a share of a long history
    # would hold back years of the latest days, so the production model would stop
    # learning long ago; a fixed count keeps training close to today whatever the
    # history length, and every model is scored on the same number of evaluation days
    # (REQ-MOD-005).
    training_samples = count_training_samples(
        symbol, len(target), features.shape[1], settings.evaluation_days
    )
    version = dataset_version(settings, symbol, prices)
    training_features = features.iloc[:training_samples]
    training_target = target.iloc[:training_samples]
    evaluation_features = features.iloc[training_samples:]
    evaluation_target = target.iloc[training_samples:]
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
    model_name = registered_model_name(symbol)
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)
    # The new model replaces production only if its error on the latest evaluation
    # days is lower than the production model's error on the same days. Only the
    # current production model competes, not every earlier version.
    promoted = _is_better_than_production(
        model_name, evaluation_features, evaluation_target, evaluation.model.mae
    )
    with mlflow.start_run():
        mlflow.log_params(
            {
                "symbol": symbol,
                "change_days": CHANGE_DAYS,
                "evaluation_days": settings.evaluation_days,
                "training_samples": training_samples,
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
        client.set_registered_model_alias(model_name, PRODUCTION_ALIAS, model_version)

    # training_samples - 1 is the last training row, training_samples the first
    # evaluation row.
    return TrainingResult(
        symbol=symbol,
        model_version=model_version,
        promoted=promoted,
        training_end=days.iloc[training_samples - 1],
        evaluation_start=days.iloc[training_samples],
        evaluation=evaluation,
    )


def _is_better_than_production(
    model_name: str,
    evaluation_features: pd.DataFrame,
    evaluation_target: pd.Series,
    new_model_mae: float,
) -> bool:
    """Tell whether the new model forecasts the evaluation days better than production.

    The current production model forecasts the same evaluation days again, from the
    same inputs, so both errors come from the same days; the error from its own
    training run, measured on older evaluation days, is never reused. A tie keeps
    production. A security without a production model takes the new model as its
    first.
    """
    # MLflow answers with the model that carries the alias production, or with an
    # error when no model of that name exists yet or none of its versions has the
    # alias.
    try:
        production_model: Any = load_model(f"models:/{model_name}@{PRODUCTION_ALIAS}")
    except MlflowException as error:
        if error.error_code in ("RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE"):
            return True
        raise
    # The production model forecasts the evaluation days the new model was scored on.
    predicted = pd.Series(
        production_model.predict(evaluation_features), index=evaluation_target.index
    )
    production_mae = float((evaluation_target - predicted).abs().mean())

    return bool(new_model_mae < production_mae)


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
    # An evaluation_days too large for the stored history would otherwise train on too
    # few samples, or score on fewer days than evaluation_days, without any error.
    if training_samples < minimum_training_samples:
        raise ValueError(
            f"{symbol} has {samples} usable samples; evaluation_days="
            f"{evaluation_days} leaves {training_samples} for training, fewer than"
            f" {minimum_training_samples}"
        )

    return training_samples
