"""Predict using a linear regression model using data from a PostgreSQL database.

This script:
  - loads latest model,
  - returns prediction for data using latest model,
  - the data is provided here in the file as EXAMPLE.

TO DO (see parts with '?'):
  - add the right paths in the beginning,
  - create .env file for user name etc. or add github secrets,
  - change data source (user gives data as input or loaded from
  somewhere with choices?).
"""

import glob
import os
from dataclasses import dataclass
from datetime import datetime

import joblib
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine

from forecasting import db
from forecasting.config import Settings

load_dotenv()  # Loads variables from the .env file

LOG_FILE = "logs/predict.logs"
MODEL_PATH = "models"


@dataclass
class ForecastResult:
    """Container for prediction results returned to API endpoints."""

    symbol: str
    prediction: float
    date: str
    model_version: str


def log_message(level: str, message: str) -> None:
    """Log messages with timestamps to console and log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"
    print(log_entry)


def predict(engine: Engine, settings: Settings, symbol: str) -> ForecastResult:
    """Run the prediction pipeline for a specific security symbol."""
    log_message("START", f"Starting prediction execution for symbol: {symbol}")

    model_files = glob.glob(os.path.join(MODEL_PATH, "linear_regression_model_*.pkl"))
    if not model_files:
        raise FileNotFoundError(
            f"No trained model files found in {MODEL_PATH} directory"
        )

    latest_model_path = max(model_files, key=os.path.getmtime)
    log_message("SUCCESS", f"Loading model from: {latest_model_path}")

    model = joblib.load(latest_model_path)

    # Fixed: db.read_prices only takes engine and symbol
    df = db.read_prices(engine, symbol=symbol)

    if df.empty:
        raise ValueError(f"No data found in the database for symbol: {symbol}")

    if "close_price" in df.columns:
        target_col = "close_price"
    elif "close price" in df.columns:
        target_col = "close price"
    else:
        target_col = df.columns[-1]

    X = df.drop(["date", target_col], axis=1, errors="ignore")
    if X.empty:
        X = df[[target_col]]

    predictions = model.predict(X)

    latest_pred = float(predictions[-1])
    latest_date = str(df["date"].iloc[-1])
    model_version = os.path.basename(latest_model_path)

    log_message("END", "Prediction finished successfully.")

    return ForecastResult(
        symbol=symbol,
        prediction=latest_pred,
        date=latest_date,
        model_version=model_version,
    )


def main() -> None:
    """CLI entry point for running predictions directly."""
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME")

    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    engine = create_engine(db_url)
    settings = Settings()  # type: ignore

    try:
        result = predict(engine, settings, symbol="AAPL")
        log_message("PREDICTIONS", f"{result}")
    except Exception as e:
        log_message("ERROR", f"An unexpected error occurred during prediction: {e!s}")
        exit(1)


if __name__ == "__main__":
    main()
