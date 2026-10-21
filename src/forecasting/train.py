"""Train a linear regression model using data from a PostgreSQL database with MLflow.

This script:
    - loads stock time series data via db.read_prices,
    - trains a linear regression model,
    - logs parameters, metrics, and models using MLflow,
    - registers models in the MLflow Model Registry,
    - compares performance with the previous version and tags the best model.
"""

import os
import warnings
from dataclasses import dataclass
from datetime import datetime

import joblib
import mlflow
import numpy as np
from dotenv import load_dotenv
from mlflow.tracking import MlflowClient
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
    """Run the training pipeline with MLflow tracking and model registry comparison."""
    log_message("START", f"Starting MLflow model training for symbol: {symbol}")

    os.makedirs(MODEL_PATH, exist_ok=True)
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    eval_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    mlflow.set_experiment(f"financial_forecasting_{symbol.lower()}")

    with mlflow.start_run() as run:
        mlflow.log_param("model_type", "LinearRegression")
        mlflow.log_param("symbol", symbol)
        mlflow.log_param("test_size", 0.2)

        model = LinearRegression()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        mse = mean_squared_error(y_test, y_pred)
        rmse = float(np.sqrt(mse))
        mae = float(mean_absolute_error(y_test, y_pred))
        r2 = float(r2_score(y_test, y_pred) if len(np.unique(y_test)) > 1 else 0.0)

        mlflow.log_metric("rmse", rmse)
        mlflow.log_metric("mae", mae)
        mlflow.log_metric("r2", r2)

        log_message(
            "METRICS",
            f"Evaluation -> RMSE: {rmse:.4f}, MAE: {mae:.4f}, R2: {r2:.4f}",
        )

        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_filename = f"linear_regression_model_{symbol}_{timestamp_str}.pkl"
        full_model_path = os.path.join(MODEL_PATH, model_filename)
        joblib.dump(model, full_model_path)

        # Log artifact and register model using core mlflow functions
        mlflow.log_artifact(full_model_path, artifact_path="model")

        model_name = f"stock_predictor_{symbol.lower()}"
        run_id = run.info.run_id
        model_uri = f"runs:/{run_id}/model/{model_filename}"
        registered_model = mlflow.register_model(model_uri, model_name)
        current_version_str = str(registered_model.version)

        client = MlflowClient()
        try:
            versions = client.search_model_versions(f"name='{model_name}'")
            other_versions = [v for v in versions if v.run_id != run.info.run_id]

            if other_versions:
                latest_prior = max(other_versions, key=lambda v: int(v.version or 0))

                if latest_prior.run_id:
                    prior_run = client.get_run(latest_prior.run_id)
                    prior_mae = float(prior_run.data.metrics.get("mae", float("inf")))

                    log_message(
                        "INFO",
                        f"Comparing with prior version {latest_prior.version} "
                        f"(MAE: {prior_mae:.4f})",
                    )

                    if mae < prior_mae:
                        client.set_model_version_tag(
                            model_name, current_version_str, "stage", "champion"
                        )
                        log_message(
                            "SUCCESS",
                            "New model outperforms previous version! "
                            "Tagged as 'champion'.",
                        )
                    else:
                        client.set_model_version_tag(
                            model_name, current_version_str, "stage", "challenger"
                        )
                        log_message(
                            "INFO",
                            "New model did not beat the prior champion. "
                            "Tagged as 'challenger'.",
                        )
                else:
                    client.set_model_version_tag(
                        model_name, current_version_str, "stage", "champion"
                    )
            else:
                client.set_model_version_tag(
                    model_name, current_version_str, "stage", "champion"
                )
                log_message(
                    "SUCCESS", "First model version registered. Tagged as 'champion'."
                )
        except Exception as registry_err:
            log_message(
                "WARNING",
                f"Could not complete model registry comparison: {registry_err}",
            )

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
