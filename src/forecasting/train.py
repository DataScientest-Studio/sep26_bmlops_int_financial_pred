"""Training of the forecasting model of one security."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

import mlflow
import pandas as pd
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException
from mlflow.sklearn import load_model, log_model
from mlflow.utils.mlflow_tags import MLFLOW_GIT_COMMIT, MLFLOW_GIT_DIRTY
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import Engine

from forecasting.config import Settings
from forecasting.datasets import dataset_version
from forecasting.db import read_prices, read_splits
from forecasting.drift_checks import check_feature_drift
from forecasting.evaluate import Evaluation, evaluate
from forecasting.features import (
    CHANGE_DAYS,
    build_features,
    build_target,
    correct_for_splits,
)
from forecasting.load import is_final
from forecasting.replay import REPLAY_PREFIX, history_database

# A regression needs about ten training samples for each number it learns, one per
# input plus one for the intercept, before its fit means anything (a common rule of
# thumb in regression). More inputs therefore need more samples.
SAMPLES_PER_INPUT = 10
# MLflow's error codes for "no model of that name" and "no version has that alias".
MISSING_MODEL_ERRORS = ("RESOURCE_DOES_NOT_EXIST", "INVALID_PARAMETER_VALUE")
EXPERIMENT_NAME = "forecasting"
REPLAY_EXPERIMENT_NAME = f"{REPLAY_PREFIX}{EXPERIMENT_NAME}"
PRODUCTION_ALIAS = "production"
# Name of the run parameter in which a training records the last day of the prices it
# used, as its last step: only a completed run records it.
PRICES_UNTIL = "prices_until"


class TrainingDecisionReason(StrEnum):
    """Why a training request trains a security, or why not."""

    TRAINING_REQUESTED = "training requested"
    NO_RECORDED_TRAINING = "no recorded training"
    FEATURE_DRIFT_FOUND = "feature drift found"
    RETRAINING_INTERVAL_REACHED = "retraining interval reached"
    NOT_NEEDED = "not needed"


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


@dataclass(frozen=True)
class TrainingDecision:
    """Whether a training request trains a security, and why.

    Attributes:
        training_decision_reason: Why the security is trained or not.
        feature_drift_p_value: P-value of the feature drift check; None when the
            security has no recorded training to compare with.
        drift_check_run_id: Id of the drift check's run in MLflow; None when no check
            ran.
    """

    training_decision_reason: TrainingDecisionReason
    feature_drift_p_value: float | None
    drift_check_run_id: str | None

    @property
    def trains(self) -> bool:
        """Tell whether the security is trained."""
        return self.training_decision_reason != TrainingDecisionReason.NOT_NEEDED


def training_experiment_name(replaying: bool) -> str:
    """Return the name of the MLflow experiment training runs are recorded in.

    @relation(REQ-DAT-003, scope=function)
    """
    return REPLAY_EXPERIMENT_NAME if replaying else EXPERIMENT_NAME


def registered_model_name(symbol: str, replaying: bool) -> str:
    """Return the name a security's models are registered under in MLflow.

    @relation(REQ-DAT-003, scope=function)
    """
    prefix = REPLAY_PREFIX if replaying else ""

    return f"{prefix}forecast-{symbol}"


def decide_training(
    engine: Engine, settings: Settings, symbol: str, only_when_needed: bool
) -> TrainingDecision:
    """Decide whether a training request trains a security, and say why.

    A security with a recorded training first gets a feature drift check, recorded in
    MLflow. A request marked only when needed trains the security only when it has no
    recorded training, when the check finds drift, or when at least
    `retraining_interval_days` stored trading days lie after its latest training; any
    other request always trains.

    @relation(REQ-MOD-006, scope=function)
    @relation(REQ-MON-001, scope=function)

    Args:
        engine: Engine of the project database; while the replay database exists,
            the decision reads that instead.
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        only_when_needed: Whether the request trains only when needed.

    Returns:
        Whether the security is trained, why, and the drift check's p-value and run.
    """
    prices, replaying = read_final_prices(engine, settings, symbol)
    prices_until = find_latest_training(settings, symbol, replaying)
    if prices_until is None:
        reason = (
            TrainingDecisionReason.NO_RECORDED_TRAINING
            if only_when_needed
            else TrainingDecisionReason.TRAINING_REQUESTED
        )

        return TrainingDecision(
            training_decision_reason=reason,
            feature_drift_p_value=None,
            drift_check_run_id=None,
        )
    drift = check_feature_drift(settings, symbol, prices, prices_until, replaying)
    # Comparing the day column with one day gives one True or False per row; sum counts
    # the True rows: the stored final trading days after the latest training's prices.
    days_after_training = int((prices["day"] > prices_until).sum())
    if not only_when_needed:
        reason = TrainingDecisionReason.TRAINING_REQUESTED
    elif drift.drift_found:
        reason = TrainingDecisionReason.FEATURE_DRIFT_FOUND
    elif days_after_training >= settings.retraining_interval_days:
        reason = TrainingDecisionReason.RETRAINING_INTERVAL_REACHED
    else:
        reason = TrainingDecisionReason.NOT_NEEDED

    return TrainingDecision(
        training_decision_reason=reason,
        feature_drift_p_value=drift.p_value,
        drift_check_run_id=drift.run_id,
    )


def train(
    engine: Engine,
    settings: Settings,
    symbol: str,
    drift_check_run_id: str | None = None,
) -> TrainingResult:
    """Train a model on the stored prices of one security and record the run in MLflow.

    The latest days are held back for evaluation; the model is fitted on all earlier
    days, scored against the persistence and mean-change baselines, registered in
    MLflow and promoted to production if it is the security's first model or has a
    lower evaluation error than the current production model on the same days.

    @relation(REQ-DAT-003, scope=function)
    @relation(REQ-DAT-006, scope=function)
    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-MOD-002, scope=function)
    @relation(REQ-MOD-003, scope=function)
    @relation(REQ-MOD-004, scope=function)
    @relation(REQ-MOD-005, scope=function)
    @relation(REQ-MOD-006, scope=function)
    @relation(REQ-MON-001, scope=function)
    @relation(REQ-SVC-002, scope=function)

    Args:
        engine: Engine of the project database; while the replay database exists,
            training reads that instead.
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        drift_check_run_id: Id of the drift check run before this training, recorded
            with the run; None when no check ran.

    Returns:
        The model version, whether it was promoted, the periods used and the
        evaluation.
    """
    prices, replaying = read_final_prices(engine, settings, symbol)
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
    model_name = registered_model_name(symbol, replaying)
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    # The experiment is named in start_run, not only set: MLflow keeps the active
    # experiment for the whole process, and the API trains in several threads.
    experiment = mlflow.set_experiment(training_experiment_name(replaying))
    # The new model replaces production only if its error on the latest evaluation
    # days is lower than the production model's error on the same days. Only the
    # current production model competes, not every earlier version.
    promoted = _is_better_than_production(
        model_name, evaluation_features, evaluation_target, evaluation.model.mae
    )
    # MLflow's standard tags mlflow.source.git.commit and mlflow.source.git.dirty hold a
    # run's code version. Tags given to start_run win over MLflow's own Git lookup, so
    # they always hold the deployment's code version; mlflow.source.git.dirty is left
    # out when it is unknown whether tracked files had uncommitted changes.
    code_tags = {MLFLOW_GIT_COMMIT: settings.code_commit}
    if settings.code_has_uncommitted_changes is not None:
        code_tags[MLFLOW_GIT_DIRTY] = str(settings.code_has_uncommitted_changes).lower()
    with mlflow.start_run(experiment_id=experiment.experiment_id, tags=code_tags):
        mlflow.log_params(
            {
                "symbol": symbol,
                "change_days": CHANGE_DAYS,
                "evaluation_days": settings.evaluation_days,
                "training_samples": training_samples,
                "dataset_version": version,
            }
        )
        if drift_check_run_id is not None:
            mlflow.set_tag("drift_check_run_id", drift_check_run_id)
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
                "mean_change_forecast": evaluation.mean_change_forecast,
            }
        )
        logged = log_model(model, name="model", registered_model_name=model_name)
        model_version = str(logged.registered_model_version)
        if promoted:
            client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
            client.set_registered_model_alias(
                model_name, PRODUCTION_ALIAS, model_version
            )
        # Set after the alias, so a run whose promotion failed never says "true"; a
        # failure inside the run marks the run itself as failed in MLflow.
        mlflow.set_tag("promoted", str(promoted).lower())
        # Logged last, so only a completed run records it: a security's latest training
        # is its latest completed run. Its drift check compares against the daily
        # changes up to this day, and the retraining interval counts the stored trading
        # days after it.
        mlflow.log_param(PRICES_UNTIL, prices["day"].iloc[-1])

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


def read_final_prices(
    engine: Engine, settings: Settings, symbol: str
) -> tuple[pd.DataFrame, bool]:
    """Read a security's prices with a final close, corrected for splits.

    @relation(REQ-MOD-001, scope=function)

    Args:
        engine: Engine of the project database; while the replay database exists,
            the prices are read from that instead.
        settings: Settings of this deployment.
        symbol: Ticker of the security.

    Returns:
        The prices, oldest first, and whether they come from the replay database.
    """
    # Callers pass a configured security: the route refuses any other symbol, the
    # commands loop over the configured ones. is_final needs its exchange to know when
    # that exchange closes.
    exchange = settings.exchange_of(symbol)
    with history_database(engine, settings) as (database, replaying):
        stored = read_prices(database, symbol)
        splits = read_splits(database, symbol)
    # One True or False per row: is that day's close final? zip walks both columns side
    # by side. stored.loc[final] keeps the True rows, so a provisional close, which may
    # still change, never enters training or a drift check.
    final = [
        is_final(exchange, day, fetched_at, settings.final_delay)
        for day, fetched_at in zip(stored["day"], stored["fetched_at"])
    ]
    # correct_for_splits expresses the final days in the shares of the latest final
    # day; a split after that day has not happened for these rows yet.
    prices = correct_for_splits(stored.loc[final], splits)

    return prices, replaying


def find_latest_training(
    settings: Settings, symbol: str, replaying: bool
) -> date | None:
    """Return the last day of the prices a security's latest completed training used.

    A completed run is finished and has recorded `PRICES_UNTIL`, its last step;
    promoted or not.

    @relation(REQ-MOD-006, scope=function)

    Args:
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        replaying: Whether the replay database exists; replay runs are recorded in
            their own experiment.

    Returns:
        The last day of the prices the latest completed training run used, or None when
        the security has no such run.
    """
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    experiment = client.get_experiment_by_name(training_experiment_name(replaying))
    # No experiment yet: nothing was ever trained.
    if experiment is None:
        return None
    # A failed run is marked FAILED; a run cut off before its last step lacks the
    # parameter, and a parameter compared with != '' leaves out every run without it.
    runs = client.search_runs(
        [experiment.experiment_id],
        filter_string=(
            f"params.symbol = '{symbol}' and attributes.status = 'FINISHED'"
            f" and params.{PRICES_UNTIL} != ''"
        ),
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    if not runs:
        return None

    return date.fromisoformat(runs[0].data.params[PRICES_UNTIL])


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
        if error.error_code in MISSING_MODEL_ERRORS:
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
