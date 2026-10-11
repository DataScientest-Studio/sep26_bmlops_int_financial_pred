"""Request and response bodies of the API."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field


class SecurityRequest(BaseModel):
    """Names the security a request is about."""

    symbol: Annotated[str, Field(min_length=1, max_length=20, examples=["AAPL"])]


class ForecastResponse(BaseModel):
    """Forecast of the next trading day's change."""

    symbol: str
    day: Annotated[date, Field(description="Trading day the forecast is for.")]
    change: Annotated[
        float, Field(description="Predicted relative close-to-close change.")
    ]
    model_version: str


class TrainingResponse(BaseModel):
    """Outcome of a training run."""

    symbol: str
    model_version: str
    evaluation_days: int
    model_mae: float
    persistence_mae: float
    mean_change_mae: float
