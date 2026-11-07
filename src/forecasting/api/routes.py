"""Endpoints of the API."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from forecasting.api.dependencies import EngineDep, SettingsDep
from forecasting.api.schemas import (
    CloseResponse,
    ForecastResponse,
    ModelResponse,
    ScoresResponse,
    SecurityRequest,
    TrainingResponse,
)
from forecasting.config import Settings
from forecasting.predict import (
    NoProductionModel,
    predict,
    production_results,
    recent_closes,
)
from forecasting.train import train

router = APIRouter()
# Most trading days of closes one history request may ask for, about four years; keeps
# one answer small.
MOST_HISTORY_DAYS = 1000


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

    A symbol that is not a configured security, or a security without a production
    model, gets 404.

    @relation(REQ-SVC-001, scope=function)
    """
    _refuse_unknown(request.symbol, settings)
    try:
        forecast = predict(engine, settings, request.symbol)
    except NoProductionModel as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

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
        promoted=result.promoted,
        evaluation_days=result.evaluation.days,
        model_mae=result.evaluation.model.mae,
        persistence_mae=result.evaluation.persistence.mae,
        mean_change_mae=result.evaluation.mean_change.mae,
    )


@router.get("/securities", response_model=list[str])
def securities_endpoint(settings: SettingsDep) -> list[str]:
    """List the configured securities a forecast can be asked for.

    @relation(REQ-SVC-005, scope=function)
    """
    return [security.symbol for security in settings.securities]


@router.get("/securities/{symbol}/history", response_model=list[CloseResponse])
def history_endpoint(
    symbol: str,
    days: Annotated[int, Query(ge=1, le=MOST_HISTORY_DAYS)],
    engine: EngineDep,
    settings: SettingsDep,
) -> list[CloseResponse]:
    """Return the closes of the security's latest stored trading days.

    A symbol that is not a configured security gets 404.

    @relation(REQ-SVC-006, scope=function)
    """
    _refuse_unknown(symbol, settings)
    closes = recent_closes(engine, settings, symbol, days)

    return [
        CloseResponse(day=day, close=close)
        for day, close in zip(closes["day"], closes["close"])
    ]


@router.get("/securities/{symbol}/model", response_model=ModelResponse)
def model_endpoint(
    symbol: str, engine: EngineDep, settings: SettingsDep
) -> ModelResponse:
    """Return the security's production model with its results next to the baselines.

    A symbol that is not a configured security, or a security without a production
    model, gets 404.

    @relation(REQ-SVC-007, scope=function)
    """
    _refuse_unknown(symbol, settings)
    try:
        results = production_results(engine, settings, symbol)
    except NoProductionModel as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return ModelResponse(
        symbol=results.symbol,
        model_version=results.model_version,
        evaluation_days=results.evaluation_days,
        model=ScoresResponse(**vars(results.model)),
        persistence=ScoresResponse(**vars(results.persistence)),
        mean_change=ScoresResponse(**vars(results.mean_change)),
        mean_change_forecast=results.mean_change_forecast,
    )
