"""Training of the forecasting model of one security."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Engine

from forecasting.config import Settings
from forecasting.evaluate import Evaluation


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
    raise NotImplementedError
