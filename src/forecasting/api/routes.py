"""Endpoints of the API."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from forecasting.api.dependencies import get_engine, get_settings
from forecasting.api.schemas import (
    ForecastResponse,
    SecurityRequest,
    TrainingResponse,
)
from forecasting.config import Settings
from forecasting.predict import predict
from forecasting.train import train

router = APIRouter()

EngineDep = Annotated[Engine, Depends(get_engine)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the service is running.

    @relation(REQ-AUT-003, scope=function)
    """
    return {"status": "ok"}


@router.post("/predict", response_model=ForecastResponse)
def predict_endpoint(
    request: SecurityRequest, engine: EngineDep, settings: SettingsDep
) -> ForecastResponse:
    """Return the production model's forecast for the next trading day.

    @relation(REQ-SVC-001, scope=function)
    """
    forecast = predict(engine, settings, request.symbol)
    return ForecastResponse(**vars(forecast))


@router.post("/training", response_model=TrainingResponse)
def training_endpoint(
    request: SecurityRequest, engine: EngineDep, settings: SettingsDep
) -> TrainingResponse:
    """Train a model for the security and report the outcome.

    @relation(REQ-SVC-002, scope=function)
    """
    result = train(engine, settings, request.symbol)
    return TrainingResponse(
        symbol=result.symbol,
        model_version=result.model_version,
        evaluation_days=result.evaluation.days,
        model_mae=result.evaluation.model.mae,
        persistence_mae=result.evaluation.persistence.mae,
        mean_change_mae=result.evaluation.mean_change.mae,
    )
