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
    raise NotImplementedError
