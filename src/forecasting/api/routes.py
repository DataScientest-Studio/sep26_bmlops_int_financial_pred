"""Endpoints of the API."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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


def _refuse_unknown(symbol: str, settings: Settings) -> None:
    """Refuse a symbol that is not one of the configured securities.

    Market indices and unknown symbols are refused alike, so a symbol from a request
    never reaches training or prediction unchecked.

    Raises:
        HTTPException: 404 if no configured security has this symbol.
    """
    if symbol not in {security.symbol for security in settings.securities}:
        raise HTTPException(status_code=404, detail=f"Unknown security: {symbol}")


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

    A symbol that is not a configured security gets 404.

    @relation(REQ-SVC-001, scope=function)
    """
    _refuse_unknown(request.symbol, settings)
    forecast = predict(engine, settings, request.symbol)
    return ForecastResponse(**vars(forecast))


@router.post("/training", response_model=TrainingResponse)
def training_endpoint(
    request: SecurityRequest, engine: EngineDep, settings: SettingsDep
) -> TrainingResponse:
    """Train a model for the security and report the outcome.

    A symbol that is not a configured security gets 404.

    @relation(REQ-SVC-002, scope=function)
    """
    _refuse_unknown(request.symbol, settings)
    result = train(engine, settings, request.symbol)
    return TrainingResponse(
        symbol=result.symbol,
        model_version=result.model_version,
        evaluation_days=result.evaluation.days,
        model_mae=result.evaluation.model.mae,
        persistence_mae=result.evaluation.persistence.mae,
        mean_change_mae=result.evaluation.mean_change.mae,
    )
