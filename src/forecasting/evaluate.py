"""Scoring of a model against the baselines."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Scores:
    """Quality of one forecaster on the evaluation days.

    Attributes:
        mae: Mean absolute error of the predicted change.
        skill: 1 − MAE / MAE of persistence; above 0 beats persistence.
        directional_accuracy: Share of days with the correct sign of the change.
    """

    mae: float
    skill: float
    directional_accuracy: float


@dataclass(frozen=True)
class Evaluation:
    """Scores of the model and both baselines on the same evaluation days.

    Attributes:
        model: Scores of the trained model.
        persistence: Scores of the forecast "no change".
        mean_change: Scores of the historical mean change of the training days.
        days: Number of evaluation days.
    """

    model: Scores
    persistence: Scores
    mean_change: Scores
    days: int


def evaluate(
    actual: pd.Series, predicted: pd.Series, training_target: pd.Series
) -> Evaluation:
    """Score the model and both baselines on the same evaluation days.

    @relation(REQ-MOD-002, scope=function)

    Args:
        actual: Actual changes on the evaluation days.
        predicted: The model's predicted changes on the same days.
        training_target: Changes of the training days, for the mean-change
            baseline.

    Returns:
        The scores of the model, persistence and the mean change.
    """
    # Persistence forecasts "tomorrow's close equals today's", a change of 0.0 on every
    # day; mean change forecasts the training days' average change on every day.
    # index=actual.index gives both baselines the row labels of actual: pandas lines
    # Series up by label, not by position, so each day is compared with its own day.
    persistence = pd.Series(0.0, index=actual.index)
    mean_change = pd.Series(training_target.mean(), index=actual.index)
    # Predicting 0 misses by the whole move, so this is the MAE of persistence: the
    # yardstick every skill is measured against.
    persistence_mae = actual.abs().mean()

    # One helper scores all three forecasters, so the same rules judge each of them
    # on the same days against the same yardstick.
    return Evaluation(
        model=_scores(actual, predicted, persistence_mae),
        persistence=_scores(actual, persistence, persistence_mae),
        mean_change=_scores(actual, mean_change, persistence_mae),
        days=len(actual),
    )


def _scores(actual: pd.Series, predicted: pd.Series, persistence_mae: float) -> Scores:
    """Score one forecaster's predicted changes against the actual changes."""
    mae = (actual - predicted).abs().mean()
    # Above 0 beats persistence, 0 ties it, below 0 is worse.
    skill = 1 - mae / persistence_mae
    # Numbers of the same sign multiply to a positive number; a forecast of 0 never
    # calls a direction, so it never hits.
    hits = predicted * actual > 0

    return Scores(mae=mae, skill=skill, directional_accuracy=hits.mean())
