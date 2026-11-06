"""Training: trains a model for each configured security when new prices arrive."""

import logging
import tomllib
from datetime import timedelta
from pathlib import Path

import pendulum
import requests
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

logger = logging.getLogger(__name__)


@dag(
    schedule=PRICES | REPLAY_PRICES,
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
)
def training():
    """Trains a model for each configured security through the API.

    Every configured security is trained even when the training of one fails; the run
    then fails and names each security whose training failed.

    @relation(REQ-AUT-001, scope=function)
    @relation(REQ-AUT-008, scope=function)
    """

    @task(execution_timeout=TRAINING_LIMIT)
    def train_securities() -> list[dict]:
        """Trains each configured security and returns the outcomes.

        A security that fails is logged at once, and the others are still trained.

        Returns:
            The outcome the API answered for each security.

        Raises:
            RuntimeError: If any security failed; names each with its reason.
        """
        outcomes = []
        failures = []
        for symbol in symbols:
            body = {"symbol": symbol}
            try:
                outcome = post_to_service(TRAINING_URL, TRAINING_LIMIT, body)
            except (RuntimeError, requests.RequestException) as error:
                # Logged at once: if the time limit stops the task, the task log still
                # shows each failure so far.
                failure = f"{symbol}: {error}"
                logger.error(failure)
                failures.append(failure)
                continue
            outcomes.append(outcome)
        if failures:
            raise RuntimeError("Training failed for " + "; ".join(failures))

        return outcomes

    train_securities()


training()
