"""Replay: copies the next stored trading day into the replay database."""

import os
from datetime import timedelta

import pendulum
import requests
from airflow.sdk import dag, task
from airflow.sdk.exceptions import AirflowSkipException
from airflow.timetables.trigger import DeltaTriggerTimetable

# The data service inside Compose; it runs the same replay as `make replay`.
REPLAY_URL = "http://data:8000/replay"

# Limits of REPLAY_INTERVAL_SECONDS.
SHORTEST_INTERVAL_SECONDS = 10
LONGEST_INTERVAL_SECONDS = 60

# The first run copies every stored day up to REPLAY_START, so it takes longest.
REPLAY_TIMEOUT = timedelta(minutes=30)

# Seconds from the start of one replayed day to the next; a value outside the limits
# stops Airflow from loading this pipeline.
interval_seconds = int(os.environ["REPLAY_INTERVAL_SECONDS"])
if not SHORTEST_INTERVAL_SECONDS <= interval_seconds <= LONGEST_INTERVAL_SECONDS:
    raise ValueError(
        f"REPLAY_INTERVAL_SECONDS is {interval_seconds};"
        f" it must be {SHORTEST_INTERVAL_SECONDS} to {LONGEST_INTERVAL_SECONDS}."
    )


@dag(
    schedule=DeltaTriggerTimetable(timedelta(seconds=interval_seconds)),
    start_date=pendulum.datetime(2026, 10, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
)
def replay():
    """Replays the stored trading days one at a time through the data service.

    @relation(REQ-AUT-001, scope=function)
    @relation(REQ-DAT-003, scope=function)
    """

    @task(execution_timeout=REPLAY_TIMEOUT)
    def replay_day() -> dict:
        """Replays the next trading day; skips once nothing is left."""
        response = requests.post(REPLAY_URL, timeout=REPLAY_TIMEOUT.total_seconds())
        response.raise_for_status()
        report = response.json()
        if report["day"] is None:
            raise AirflowSkipException("Nothing left to replay; pause the pipeline.")

        return report

    replay_day()


replay()
