"""Training: trains a model for each configured security when new prices arrive."""

import tomllib
from datetime import timedelta
from pathlib import Path

import pendulum
import requests
from airflow.sdk import Asset, dag, task

# The API inside Compose; it runs the same training as `make train`.
TRAINING_URL = "http://api:8000/training"

# Announced by the daily update and the replay pipeline when new prices are stored.
PRICES = Asset("prices")
REPLAY_PRICES = Asset("replay-prices")

# Configured securities to train a model for.
SECURITIES_FILE = Path(__file__).resolve().parents[2] / "config" / "securities.toml"
with SECURITIES_FILE.open("rb") as file:
    SYMBOLS = tuple(entry["symbol"] for entry in tomllib.load(file)["securities"])

# One run trains a model and records its dataset version and run in MLflow for each
# configured security.
TRAINING_TIMEOUT = timedelta(minutes=30)


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
    @relation(REQ-MOD-004, scope=function)
    @relation(REQ-MOD-005, scope=function)
    """

    @task(execution_timeout=TRAINING_TIMEOUT)
    def train_securities() -> list[dict]:
        """Trains each configured security and returns the outcomes."""
        outcomes = []
        for symbol in SYMBOLS:
            response = requests.post(
                TRAINING_URL,
                json={"symbol": symbol},
                timeout=TRAINING_TIMEOUT.total_seconds(),
            )
            if not response.ok:
                answer = f"{response.status_code}: {response.text}"
                raise RuntimeError(f"The API answered {answer}")
            outcomes.append(response.json())

        return outcomes

    train_securities()


training()
