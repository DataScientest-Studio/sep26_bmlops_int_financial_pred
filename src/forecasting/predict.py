"""Forecast of the next trading day's change of one security."""

from dataclasses import dataclass
from datetime import date, datetime

import joblib
from sqlalchemy import Engine

from forecasting.config import Settings
from forecasting.db import read_prices
from forecasting.features import build_features
from forecasting.trading_calendar import next_trading_day


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
    prices = read_prices(engine, symbol)
    # The latest stored day, as one row; the forecast starts from its close, which may
    # still be provisional.
    latest = prices.iloc[-1]
    # Model files are named by the UTC time of their training run, and such names sort
    # in time order, so the largest name is the newest model.
    model_file = max((settings.model_dir / symbol).glob("*.joblib"))
    model = joblib.load(model_file)
    # The model is a formula over the features, so it needs today's values of them.
    # build_features computes every day exactly as in training; the longest volatility
    # window needs that many changes, plus one close before them. The double brackets
    # keep the latest row as a one-row table, the shape predict expects.
    features = build_features(prices).iloc[[-1]]
    # predict returns one value per row; [0] takes the only one, float turns numpy's
    # number into a plain Python float.
    change = float(model.predict(features)[0])

    # The file name without .joblib (stem) is the model version. The forecast is for
    # the next trading day: the exchange's calendar skips weekends and holidays, so a
    # Friday close forecasts Monday.
    return Forecast(
        symbol=symbol,
        day=next_trading_day(settings.exchange_of(symbol), latest["day"]),
        change=change,
        model_version=model_file.stem,
        start_close=float(latest["close"]),
        start_fetched_at=latest["fetched_at"],
    )
