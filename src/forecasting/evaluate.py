"""Scoring of a model against the baselines."""

from dataclasses import dataclass
import numpy as np
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
    actual_arr = np.asarray(actual).flatten()
    pred_arr = np.asarray(predicted).flatten()
    train_arr = np.asarray(training_target).flatten()

    # Baselines
    persistence_arr = np.zeros_like(actual_arr)
    mean_val = float(np.mean(train_arr)) if len(train_arr) > 0 else 0.0
    mean_change_arr = np.full_like(actual_arr, mean_val)

    def compute_scores(pred, persistence_mae_ref=None):
        mae = float(np.mean(np.abs(actual_arr - pred)))
        
        # Directional accuracy: share of days with correct sign match
        dir_acc = float(np.mean(np.sign(actual_arr) == np.sign(pred)))
        
        if persistence_mae_ref is None:
            skill = 0.0
        else:
            if persistence_mae_ref == 0:
                skill = 0.0
            else:
                skill = float(1.0 - (mae / persistence_mae_ref))
        return mae, skill, dir_acc

    # 1. Persistence scores
    p_mae, _, p_dir = compute_scores(persistence_arr)
    p_skill = 0.0  # persistence skill relative to itself is 0

    # 2. Model scores (using persistence MAE as reference for skill)
    m_mae, m_skill, m_dir = compute_scores(pred_arr, persistence_mae_ref=p_mae)

    # 3. Mean change scores
    mc_mae, mc_skill, mc_dir = compute_scores(mean_change_arr, persistence_mae_ref=p_mae)

    days = len(actual_arr)

    return Evaluation(
        model=Scores(mae=m_mae, skill=m_skill, directional_accuracy=m_dir),
        persistence=Scores(mae=p_mae, skill=p_skill, directional_accuracy=p_dir),
        mean_change=Scores(mae=mc_mae, skill=mc_skill, directional_accuracy=mc_dir),
        days=days,
    )