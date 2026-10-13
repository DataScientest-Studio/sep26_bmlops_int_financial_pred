"""Forecast of the next trading day's change of one security."""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Engine

from forecasting.config import Settings


@dataclass(frozen=True)
class Forecast:
    """A forecast for one security.

    @relation(REQ-SVC-001, scope=class)

    Attributes:
        symbol: Ticker of the security.
        day: The trading day the forecast is for.
        change: Predicted relative close-to-close change to `day`.
        model_version: Identifier of the model that produced it.
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


def predict(engine: Engine, settings: Settings, symbol: str) -> Forecast:
    """Forecast the change from the latest stored day to the next trading day.

    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-SVC-001, scope=function)

    Args:
        engine: Engine of the project database.
        settings: Settings; the model is read from `settings.model_dir`.
        symbol: Ticker of the security.

    Returns:
        The forecast with the version of the model that produced it, and the close it
        starts from with the time that close was fetched.
    """
    raise NotImplementedError
