"""Forecast of the next trading day's change of one security."""

import glob
import os
from dataclasses import dataclass
from datetime import date, datetime

import joblib
import pandas as pd
from sqlalchemy import Engine

from forecasting import db
from forecasting.config import Settings

MODEL_PATH = "models"


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


def log_message(level: str, message: str) -> None:
    """Log a message with a timestamp to standard output."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"
    print(log_entry)


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
    log_message("START", f"Starting prediction execution for symbol: {symbol}")

    model_files = glob.glob(
        os.path.join(MODEL_PATH, f"linear_regression_model_{symbol.upper()}_*.pkl")
    )
    if not model_files:
        raise FileNotFoundError(
            f"No trained model files found in {MODEL_PATH} directory"
        )

    # Or fetch the latest model file matching that symbol from your models directory
    latest_model_path = max(model_files, key=os.path.getmtime)
    log_message("SUCCESS", f"Loading model from: {latest_model_path}")

    model, sc = joblib.load(latest_model_path)

    df = db.read_prices(engine, symbol=symbol)
    df = pd.DataFrame(df)
    if df.empty:
        raise ValueError(f"No data found in the database for symbol: {symbol}")

    # CHANGED TARGET VARIABLE
    df["return"] = df["close"].pct_change()
    df = df.dropna()

    target_col = "return"

    # 2. Drop day, close, and return from features
    X = df.drop(["day", "close", target_col], axis=1, errors="ignore")
    X = X.select_dtypes(include=["number"])

    if X.empty:
        X = df[[]]

    # Scale X using the exact same scaler fitted during training
    X_scaled = sc.transform(X)

    predictions = model.predict(X_scaled)

    latest_pred = float(predictions[-1].item())

    # Get the last date from the dataframe as a date object
    last_date = pd.to_datetime(df["day"].iloc[-1]).date()
    next_trading_day = (pd.Timestamp(last_date) + pd.offsets.BDay(1)).date()

    # Handle New Year's Day holiday edge case
    if next_trading_day.month == 1 and next_trading_day.day == 1:
        next_trading_day = (
            pd.Timestamp(next_trading_day) + pd.Timedelta(days=1)
        ).date()

    # latest_date = date.fromisoformat(str(df["day"].iloc[-1]))
    model_version = os.path.basename(latest_model_path)

    log_message("END", "Prediction finished successfully.")

    return Forecast(
        symbol=symbol,
        day=next_trading_day,
        change=latest_pred,
        model_version=model_version,
        start_close=float(df["close"].iloc[-1]),
        start_fetched_at=pd.to_datetime(df["fetched_at"].iloc[-1]),
    )
