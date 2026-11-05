"""Request and response bodies of the API."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field


class SecurityRequest(BaseModel):
    """Names the security a request is about."""

    symbol: Annotated[str, Field(min_length=1, max_length=20, examples=["AAPL.US"])]


class ForecastResponse(BaseModel):
    """Forecast of the next trading day's change.

    @relation(REQ-SVC-001, scope=class)
    """

    symbol: str
    day: Annotated[date, Field(description="Trading day the forecast is for.")]
    change: Annotated[
        float, Field(description="Predicted relative close-to-close change.")
    ]
    model_version: str
    start_close: Annotated[
        float, Field(description="Close the change starts from; may be provisional.")
    ]
    start_fetched_at: Annotated[
        datetime, Field(description="When that close was fetched.")
    ]


class TrainingResponse(BaseModel):
    """Outcome of a training run."""

    symbol: str
    model_version: str
    promoted: bool
    evaluation_days: int
    model_mae: float
    persistence_mae: float
    mean_change_mae: float
