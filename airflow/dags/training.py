"""Training: trains each configured security when needed, then forecasts it."""

from datetime import timedelta

import pendulum
from airflow.sdk import Asset, dag, task
from service_call import fail_on_failures, post_for_each_security

# The API inside Compose; it runs the same training as `make train` and the same
# forecast as `make predict`.
TRAINING_URL = "http://api:8000/training"
FORECAST_URL = "http://api:8000/predict"

# Announced by the daily update after each load and the replay after each replayed day.
PRICES = Asset("prices")
REPLAY_PRICES = Asset("replay-prices")
# Announced by the prediction drift check when it finds drift.
PREDICTION_DRIFT_FOUND = Asset("prediction-drift-found")
# Announced after the forecasts, so the prediction drift check starts on them.
SCHEDULED_FORECASTS = Asset("scheduled-forecasts")

# Time limit of the training task, long enough to train every configured security one
# after the other.
TRAINING_LIMIT = timedelta(minutes=30)
# Time limit of the forecast task, long enough to forecast each configured security one
# after the other.
FORECAST_LIMIT = timedelta(minutes=10)


@dag(
    schedule=PRICES | REPLAY_PRICES | PREDICTION_DRIFT_FOUND,
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
)
def training():
    """Trains each configured security when needed, then makes its scheduled forecast.

    A run started by drift in the forecasts trains every security; any other run trains
    a security only when needed. The run goes through every configured security even
    when one security fails. For each security it trains the model when needed and then
    makes the forecast. At the end the run fails and names each security whose training
    or forecast failed.

    @relation(REQ-AUT-001, scope=function)
    @relation(REQ-AUT-008, scope=function)
    @relation(REQ-MOD-006, scope=function)
    @relation(REQ-MON-002, scope=function)
    """

    @task(execution_timeout=TRAINING_LIMIT)
    def train_securities(triggering_asset_events=None) -> dict:
        """Trains each configured security as needed; returns answers and failures."""
        # triggering_asset_events holds, for each asset, the announcements that started
        # this run; an asset that did not start the run has an empty list.
        started_by_drift = bool(triggering_asset_events[PREDICTION_DRIFT_FOUND])
        only_when_needed = not started_by_drift
        fields = {"only_when_needed": only_when_needed}

        return post_for_each_security(TRAINING_URL, TRAINING_LIMIT, fields)

    @task(execution_timeout=FORECAST_LIMIT, outlets=[SCHEDULED_FORECASTS])
    def forecast_securities() -> dict:
        """Makes each security's scheduled forecast; returns answers and failures."""
        fields = {"scheduled": True}

        return post_for_each_security(FORECAST_URL, FORECAST_LIMIT, fields)

    @task
    def report_failures(trainings: dict, forecasts: dict) -> None:
        """Fails the run if any security failed, naming each with its reason."""
        fail_on_failures(trainings["failures"] + forecasts["failures"])

    trainings = train_securities()
    forecasts = forecast_securities()
    trainings >> forecasts
    report_failures(trainings, forecasts)


training()
