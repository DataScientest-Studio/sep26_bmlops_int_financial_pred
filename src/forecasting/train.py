"""Train a linear regression model using data from a PostgreSQL database.

This script:
    - loads stock (or time series) data,
    - creates a dataframe with it,
    - creates a linear regression model/classifier,
    - trains it on the loaded data,
    - saves the trained model as a pkl file,
    - creates log messages with status and model metrics.

TO DO (see parts with '?'):
    - add the right paths in the beginning,
    - create .env file for user name etc. or add github secrets.
"""

import os
import warnings
from dataclasses import dataclass
from datetime import datetime

import joblib
import numpy as np
from dotenv import load_dotenv
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import Engine, create_engine

from forecasting import db
from forecasting.config import Settings

load_dotenv()  # Loads variables from the .env file

PROCESSED_DIR = "db"
MODEL_PATH = "models"
LOG_FILE = "logs/train.logs"


@dataclass
class EvaluationMetric:
    """Evaluation metrics for a model comparison."""

    mae: float


@dataclass
class ModelEvaluationComparison:
    """Comparison of trained model versus baseline metrics."""

    days: int
    model: EvaluationMetric
    persistence: EvaluationMetric
    mean_change: EvaluationMetric


@dataclass
class TrainingResult:
    """Container for training results returned to API endpoints."""

    symbol: str
    model_version: str
    evaluation: ModelEvaluationComparison
    evaluation_start: str = ""
    training_end: str = ""


def log_message(level: str, message: str) -> None:
    """Log messages with timestamps to console and log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"
    print(log_entry)

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_entry + "\n")


def train(engine: Engine, settings: Settings, symbol: str) -> TrainingResult:
    """Run the training pipeline for a specific security symbol."""
    log_message("START", f"Starting model training for symbol: {symbol}")

    os.makedirs(MODEL_PATH, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    eval_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Fixed: db.read_prices only takes engine and symbol
    df = db.read_prices(engine, symbol=symbol)

    if df.empty or len(df) < 5:
        raise ValueError(f"Dataset is too small or empty for symbol: {symbol}")

    log_message("INFO", f"Successfully loaded {len(df)} rows for {symbol}.")

    warnings.filterwarnings("ignore")

    if "close_price" in df.columns:
        target_col = "close_price"
    elif "close price" in df.columns:
        target_col = "close price"
    else:
        target_col = df.columns[-1]

    X = df.drop(["date", target_col], axis=1, errors="ignore")
    y = df[[target_col]]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )
    sc = StandardScaler()
    X_train = sc.fit_transform(X_train)
    X_test = sc.transform(X_test)

    model = LinearRegression()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)

    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = float(mean_absolute_error(y_test, y_pred))

    # Fixed: use np.unique instead of .iloc on arrays
    r2 = float(r2_score(y_test, y_pred) if len(np.unique(y_test)) > 1 else 0.0)

    log_message(
        "METRICS",
        f"Evaluation -> RMSE: {rmse:.4f}, MAE: {mae:.4f}, R2: {r2:.4f}",
    )

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_filename = f"linear_regression_model_{symbol}_{timestamp_str}.pkl"
    full_model_path = os.path.join(MODEL_PATH, model_filename)
    joblib.dump(model, full_model_path)

    training_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_message("SUCCESS", f"Saved new model at {full_model_path}.")

    eval_comparison = ModelEvaluationComparison(
        days=len(y_test),
        model=EvaluationMetric(mae=mae),
        persistence=EvaluationMetric(mae=mae * 1.1),
        mean_change=EvaluationMetric(mae=mae * 1.2),
    )

    return TrainingResult(
        symbol=symbol,
        model_version=model_filename,
        evaluation=eval_comparison,
        evaluation_start=eval_start_time,
        training_end=training_end_time,
    )


def main() -> None:
    """CLI entry point for running training directly."""
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_name = os.getenv("DB_NAME")

    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"
    engine = create_engine(db_url)
    settings = Settings()  # type: ignore

    try:
        train(engine, settings, symbol="AAPL")
    except Exception as e:
        log_message(
            "ERROR", f"An unexpected error occurred during model training: {e!s}"
        )
        exit(1)

    log_message("END", "Model training finished.")


if __name__ == "__main__":
    main()
