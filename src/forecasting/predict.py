"""Forecast of the next trading day's change of one security."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import Engine

from forecasting.config import Settings


@dataclass(frozen=True)
class Forecast:
    """A forecast for one security.

    Attributes:
        symbol: Ticker of the security.
        day: The trading day the forecast is for.
        change: Predicted relative close-to-close change to `day`.
        model_version: Identifier of the model that produced it.
    """

    symbol: str
    day: date
    change: float
    model_version: str


def predict(engine: Engine, settings: Settings, symbol: str) -> Forecast:
    """Forecast the change from the latest stored day to the next trading day.

    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-SVC-001, scope=function)

    Args:
        engine: Engine of the project database.
        settings: Settings; the model is read from `settings.model_dir`.
        symbol: Ticker of the security.

    Returns:
        The forecast with the version of the model that produced it.
    """
    raise NotImplementedError
