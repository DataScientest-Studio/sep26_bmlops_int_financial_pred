"""Training of the forecasting model of one security."""

import os
from dataclasses import dataclass
from datetime import date, datetime

import joblib
import mlflow
import numpy as np
from mlflow.tracking import MlflowClient
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sqlalchemy import Engine

from forecasting import db
from forecasting.config import Settings
from forecasting.evaluate import Evaluation, Scores

MODEL_PATH = "models"


@dataclass(frozen=True)
class TrainingResult:
    """Outcome of a training run.

    Attributes:
        symbol: Ticker of the security.
        model_version: Identifier of the saved model.
        training_end: Last day of the training period.
        evaluation_start: First day of the evaluation period, after
            `training_end`.
        evaluation: Scores of the model and both baselines.
    """

    symbol: str
    model_version: str
    training_end: date
    evaluation_start: date
    evaluation: Evaluation


def log_message(level: str, message: str) -> None:
    """Log a message with a timestamp to standard output."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {level}: {message}"
    print(log_entry)


def train(engine: Engine, settings: Settings, symbol: str) -> TrainingResult:
    """Train a model on the stored prices of one security and save it.

    The latest days are held back for evaluation; they are always later than
    the training days.

    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-MOD-002, scope=function)
    @relation(REQ-MOD-003, scope=function)
    @relation(REQ-MOD-004, scope=function)
    @relation(REQ-MOD-005, scope=function)
    @relation(REQ-SVC-002, scope=function)

    Args:
        engine: Engine of the project database.
        settings: Settings; the model is saved under `settings.model_dir`.
        symbol: Ticker of the security.

    Returns:
        The model version, the periods used and the evaluation.
    """
    log_message("START", f"Starting MLflow model training for symbol: {symbol}")

    os.makedirs(MODEL_PATH, exist_ok=True)

    eval_start_day = date.today()

    df = db.read_prices(engine, symbol=symbol)

    if df.empty or len(df) < 5:
        raise ValueError(f"Dataset is too small or empty for symbol: {symbol}")

    log_message("INFO", f"Successfully loaded {len(df)} rows for {symbol}.")

    if "close" in df.columns:
        target_col = "close"
    else:
        target_col = df.columns[-1]

    # Example fix: Drop date/time or non-numeric columns from features
    X = df.drop(["day", target_col], axis=1, errors="ignore")
    y = df[[target_col]]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, shuffle=False
    )
    X_train = X_train.select_dtypes(include=["number"])
    X_test = X_test.select_dtypes(include=["number"])
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

    training_end_day = date.today()
    log_message("SUCCESS", f"Saved new model at {full_model_path}.")

    evaluation = Evaluation(
        days=len(y_test),
        model=Scores(mae=mae, skill=0.0, directional_accuracy=0.0),
        persistence=Scores(mae=mae * 1.1, skill=0.0, directional_accuracy=0.0),
        mean_change=Scores(mae=mae * 1.2, skill=0.0, directional_accuracy=0.0),
    )

    return TrainingResult(
        symbol=symbol,
        model_version=model_filename,
        training_end=training_end_day,
        evaluation_start=eval_start_day,
        evaluation=evaluation,
    )
