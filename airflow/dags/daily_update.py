"""Daily update: loads the new trading days on every weekday after the US close."""

import os
from datetime import timedelta

import pendulum
import requests
from airflow.sdk import Asset, dag, task
from airflow.sdk.exceptions import AirflowSkipException
from airflow.timetables.trigger import CronTriggerTimetable

# The data service inside Compose; it runs the same load as `make update`.
LOAD_URL = "http://data:8000/load"

# Announced after each load, so a pipeline waiting for new prices starts on it.
PRICES = Asset("prices")

# The US exchanges close at 16:00 New York time.
NEW_YORK = "America/New_York"
US_CLOSE_HOUR = 16

# A load makes at most 20 EODHD calls of at most 60 seconds each.
LOAD_TIMEOUT = timedelta(minutes=30)

# The load starts FINAL_DELAY_MINUTES after the close, so the day's closes are final;
# minutes past 60 move on to the next hour (a delay of 60 gives 17:00).
hour, minute = divmod(US_CLOSE_HOUR * 60 + int(os.environ["FINAL_DELAY_MINUTES"]), 60)


@dag(
    schedule=CronTriggerTimetable(f"{minute} {hour} * * 1-5", timezone=NEW_YORK),
    start_date=pendulum.datetime(2026, 10, 1, tz=NEW_YORK),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
)
def daily_update():
    """Loads the new trading days through the data service.

    @relation(REQ-AUT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)
    """

    @task(execution_timeout=LOAD_TIMEOUT, outlets=[PRICES])
    def load(dag_run=None) -> dict:
        """Runs one load and returns its report; skips a run due on an earlier day."""
        # Airflow makes up the latest missed run when it starts; on a later New York
        # day it is skipped, so at most one load runs per day.
        due_day = pendulum.instance(dag_run.run_after).in_timezone(NEW_YORK).date()
        if due_day != pendulum.now(NEW_YORK).date():
            raise AirflowSkipException(f"Due on {due_day}; a missed run is skipped.")
        response = requests.post(LOAD_URL, timeout=LOAD_TIMEOUT.total_seconds())
        response.raise_for_status()

        return response.json()

    load()


daily_update()
