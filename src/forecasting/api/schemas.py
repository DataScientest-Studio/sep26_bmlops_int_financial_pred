"""Request and response bodies of the API."""

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field


class SecurityRequest(BaseModel):
    """Names the security a request is about.

    @relation(REQ-SVC-001, REQ-SVC-002, scope=class)
    """

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
    """Outcome of a training run.

    @relation(REQ-SVC-002, scope=class)
    """

    symbol: str
    model_version: str
    promoted: bool
    evaluation_days: int
    model_mae: float
    persistence_mae: float
    mean_change_mae: float


class CloseResponse(BaseModel):
    """Close of one stored trading day, corrected for splits.

    @relation(REQ-SVC-006, scope=class)
    """

    day: date
    close: float


class ScoresResponse(BaseModel):
    """Scores of one forecaster on the evaluation days.

    @relation(REQ-SVC-007, scope=class)
    """

    mae: Annotated[float, Field(description="Mean absolute error of the change.")]
    skill: Annotated[float, Field(description="1 - MAE / MAE of persistence.")]
    directional_accuracy: Annotated[
        float, Field(description="Share of days with the correct sign of the change.")
    ]


class ModelResponse(BaseModel):
    """A security's production model and its results next to the baselines.

    @relation(REQ-SVC-007, scope=class)
    """

    symbol: str
    model_version: str
    evaluation_days: int
    model: ScoresResponse
    persistence: ScoresResponse
    mean_change: ScoresResponse
    mean_change_forecast: Annotated[
        float | None,
        Field(
            description=(
                "Change the mean-change baseline forecasts for every day; null when "
                "the model's training run did not record it."
            )
        ),
    ]
