"""Training of the forecasting model of one security."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sqlalchemy import Engine

from forecasting.config import Settings
from forecasting.db import read_prices
from forecasting.evaluate import Evaluation, evaluate
from forecasting.features import build_features, build_target
from forecasting.load import is_final

# A regression needs about ten training samples for each number it learns, one per
# input plus one for the intercept, before its fit means anything (a common rule of
# thumb in regression). More inputs therefore need more samples.
SAMPLES_PER_INPUT = 10


@dataclass(frozen=True)
class TrainingResult:
    """Outcome of a training run.

    Attributes:
        symbol: Ticker of the security.
        model_version: Identifier of the saved model.
        training_end: Last day of the training period.
        evaluation_start: First day of the evaluation period, after
            `training_end`.
        evaluation: Scores of the model and both baselines.
    """

    symbol: str
    model_version: str
    training_end: date
    evaluation_start: date
    evaluation: Evaluation


def train(engine: Engine, settings: Settings, symbol: str) -> TrainingResult:
    """Train a model on the stored prices of one security and save it.

    The latest days are held back for evaluation; they are always later than
    the training days.

    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-MOD-002, scope=function)
    @relation(REQ-MOD-003, scope=function)
    @relation(REQ-SVC-002, scope=function)

    Args:
        engine: Engine of the project database.
        settings: Settings; the model is saved under `settings.model_dir`.
        symbol: Ticker of the security.

    Returns:
        The model version, the periods used and the evaluation.
    """
    # Callers pass a configured security: the route refuses any other symbol, the
    # commands loop over the configured ones. is_final needs its exchange to know when
    # that exchange closes.
    exchange = settings.exchange_of(symbol)
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
    # The UTC time of the training run names the model file and is its version; names
    # of this form sort in time order, so the newest model is the last name.
    model_version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder = settings.model_dir / symbol
    # Creates models/<symbol>/ on the first training run; afterwards does nothing.
    folder.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, folder / f"{model_version}.joblib")

    # split - 1 is the last training row, split the first evaluation row.
    return TrainingResult(
        symbol=symbol,
        model_version=model_version,
        training_end=days.iloc[split - 1],
        evaluation_start=days.iloc[split],
        evaluation=evaluate(evaluation_target, predicted, training_target),
    )


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
