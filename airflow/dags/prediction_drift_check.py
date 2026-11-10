"""Prediction drift check: checks each configured security's scheduled forecasts."""

from datetime import timedelta

import pendulum
from airflow.sdk import Asset, TriggerRule, dag, task
from airflow.sdk.exceptions import AirflowSkipException
from service_call import fail_on_failures, post_for_each_security

# The API inside Compose; it decides whether a check is due.
CHECK_URL = "http://api:8000/prediction-drift-check"

# Announced by the training pipeline after its forecasts.
SCHEDULED_FORECASTS = Asset("scheduled-forecasts")
# Announced when a check finds drift, so the training pipeline trains every security.
PREDICTION_DRIFT_FOUND = Asset("prediction-drift-found")

# Time limit of the check task, long enough to check each configured security one
# after the other.
CHECK_LIMIT = timedelta(minutes=10)


@dag(
    schedule=SCHEDULED_FORECASTS,
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
)
def prediction_drift_check():
    """Checks the scheduled forecasts of each configured security for drift.

    The API decides whether a check is due. When any check finds drift, the run
    announces it. The run asks for the check of every configured security even when one
    check ends in an error; it then fails and names each security whose check ended in
    an error.

    @relation(REQ-AUT-001, scope=function)
    @relation(REQ-MON-002, scope=function)
    """

    @task(execution_timeout=CHECK_LIMIT)
    def check_securities() -> dict:
        """Asks for each security's check; returns answers and failures."""
        return post_for_each_security(CHECK_URL, CHECK_LIMIT)

    @task(outlets=[PREDICTION_DRIFT_FOUND])
    def announce_drift(checks: dict) -> list[str]:
        """Announces drift when any check found it; skips otherwise."""
        drifted = [
            answer["symbol"]
            for answer in checks["answers"]
            if answer["prediction_drift_found"]
        ]
        # A skipped task announces nothing.
        if not drifted:
            raise AirflowSkipException("No check found drift.")

        return drifted

    # Runs after the announcement, also when it was skipped: drift that some checks
    # found is announced before a check that ended in an error fails the run.
    @task(trigger_rule=TriggerRule.NONE_FAILED)
    def report_failures(checks: dict) -> None:
        """Fails the run if any check failed, naming each security with its reason."""
        fail_on_failures(checks["failures"])

    checks = check_securities()
    announce_drift(checks) >> report_failures(checks)


prediction_drift_check()
