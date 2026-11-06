"""Daily update: loads the new trading days as config/daily_update.toml schedules."""

import tomllib
from datetime import time, timedelta
from pathlib import Path

import pendulum
from airflow.sdk import Asset, dag, task
from airflow.sdk.exceptions import AirflowSkipException
from airflow.timetables.trigger import CronTriggerTimetable
from service_call import post_to_service

# The data service inside Compose; it runs the same load as `make update`.
LOAD_URL = "http://data:8000/load"

# Announced after each load, so a pipeline waiting for new prices starts on it.
PRICES = Asset("prices")

# The project's config/daily_update.toml, mounted read-only by compose.yaml.
DAILY_UPDATE_FILE = Path("/opt/airflow/project-config/daily_update.toml")

with DAILY_UPDATE_FILE.open("rb") as file:
    schedule = tomllib.load(file)
timezone = schedule["timezone"]
load_limit = timedelta(minutes=schedule["load_limit_minutes"])

# The load starts final_delay_minutes after start_after, so the day's closes are final;
# minutes past 60 move on to the next hour.
start = time.fromisoformat(schedule["start_after"])
delay = schedule["final_delay_minutes"]
hour, minute = divmod(start.hour * 60 + start.minute + delay, 60)
# Cron takes the days as the same numbers, separated by commas.
days = ",".join(str(day) for day in schedule["weekdays"])


@dag(
    schedule=CronTriggerTimetable(f"{minute} {hour} * * {days}", timezone=timezone),
    start_date=pendulum.datetime(2026, 10, 1, tz=timezone),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
)
def daily_update():
    """Loads the new trading days through the data service.

    @relation(REQ-AUT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)
    """

    @task(execution_timeout=load_limit, outlets=[PRICES])
    def load(dag_run=None) -> dict:
        """Runs one load and returns its report; skips a run due on an earlier day."""
        # Airflow makes up the latest missed run when it starts; on a later day in the
        # schedule's time zone it is skipped, so at most one load runs per day.
        due_day = pendulum.instance(dag_run.run_after).in_timezone(timezone).date()
        if due_day != pendulum.now(timezone).date():
            raise AirflowSkipException(f"Due on {due_day}; a missed run is skipped.")

        return post_to_service(LOAD_URL, load_limit)

    load()


daily_update()
