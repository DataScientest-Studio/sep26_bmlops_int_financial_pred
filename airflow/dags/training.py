"""Training: trains a model for each configured security when new prices arrive."""

import tomllib
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import Asset, dag, task
from service_call import post_to_service

# The API inside Compose; it runs the same training as `make train`.
TRAINING_URL = "http://api:8000/training"

# Announced by the daily update after each load and the replay after each replayed day.
PRICES = Asset("prices")
REPLAY_PRICES = Asset("replay-prices")

# One run trains every configured security, one after the other.
TRAINING_LIMIT = timedelta(minutes=30)

# The project's config/securities.toml, mounted read-only by compose.yaml.
SECURITIES_FILE = Path("/opt/airflow/project-config/securities.toml")

with SECURITIES_FILE.open("rb") as file:
    symbols = [entry["symbol"] for entry in tomllib.load(file)["securities"]]


@dag(
    schedule=PRICES | REPLAY_PRICES,
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
)
def training():
    """Trains a model for each configured security through the API.

    @relation(REQ-AUT-001, scope=function)
    """

    @task(execution_timeout=TRAINING_LIMIT)
    def train_securities() -> list[dict]:
        """Trains each configured security and returns the outcomes."""
        outcomes = []
        for symbol in symbols:
            outcome = post_to_service(TRAINING_URL, TRAINING_LIMIT, {"symbol": symbol})
            outcomes.append(outcome)

        return outcomes

    train_securities()


training()
