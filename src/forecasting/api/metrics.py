"""Numbers the API reports to Prometheus."""

import json
import logging
import time
from datetime import UTC, date, datetime, timedelta
from itertools import product
from typing import Any

import httpx2
import psycopg
from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    generate_latest,
)
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError

from forecasting.api.dependencies import EngineDep, SettingsDep
from forecasting.config import DailyUpdate, Settings
from forecasting.db import database_exists, read_latest_days, read_latest_loads
from forecasting.drift_checks import DriftKind, drift_checks_experiment_name
from forecasting.load import is_final
from forecasting.trading_calendar import next_trading_day

logger = logging.getLogger(__name__)

# Upper bounds, in seconds, of the steps response times are sorted into; they reach from
# a quick prediction up to a training run.
RESPONSE_TIME_STEPS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)
# Seconds all MLflow requests of one collection may take together. Without a limit, a
# slow or stopped MLflow would hold up the whole `/metrics` text: Prometheus gives up on
# a collection after 10 seconds (its default) and then records none of the API's
# numbers, not even the request numbers, and shows the API as down. The limit leaves the
# other numbers enough time to arrive.
DRIFT_READ_TIME_LIMIT = 3.0


def add_metrics(app: FastAPI) -> None:
    """Count requests; report them, data freshness and drift checks at `/metrics`.

    Each application keeps its request numbers in a registry of its own, so applications
    never share counts.

    @relation(REQ-MON-003, scope=function)

    Args:
        app: The API to measure.
    """
    registry = CollectorRegistry()
    # The health check and Prometheus call these routes on a timer; counting them would
    # drown the requests of users.
    instrumentator = Instrumentator(
        excluded_handlers=["/health", "/metrics"],
        registry=registry,
    )
    instrumentator.instrument(app, latency_lowr_buckets=RESPONSE_TIME_STEPS)

    @app.get("/metrics", include_in_schema=False)
    def metrics(engine: EngineDep, settings: SettingsDep) -> Response:
        """Report the API's numbers in the text format Prometheus collects."""
        numbers = generate_latest(registry)
        try:
            replaying = database_exists(settings.replay_database_url)
        except (OperationalError, psycopg.OperationalError):
            logger.exception(
                "Trading days behind, missed daily updates and drift checks left out: "
                "the database cannot be read."
            )
        else:
            numbers += report_freshness(engine, settings, datetime.now(UTC), replaying)
            numbers += report_drift_checks(settings, replaying)

        return Response(numbers, media_type=CONTENT_TYPE_LATEST)


def report_freshness(
    engine: Engine, settings: Settings, now: datetime, replaying: bool
) -> bytes:
    """Report the trading days behind and the missed daily updates, measured anew.

    A number that cannot be measured is left out: all of them while the database cannot
    be read; the missed daily updates also while the replay database exists and before
    the first load.

    @relation(REQ-MON-003, scope=function)
    @relation(REQ-MON-004, scope=function)

    Args:
        engine: Engine of the project database.
        settings: Settings of this deployment.
        now: Time to measure at, timezone-aware.
        replaying: Whether the replay database exists.

    Returns:
        The numbers in the text format Prometheus collects.
    """
    registry = CollectorRegistry()
    try:
        latest_days = read_latest_days(engine)
        latest_loads = read_latest_loads(engine)
    except (OperationalError, psycopg.OperationalError):
        logger.exception(
            "Trading days behind and missed daily updates left out: "
            "the database cannot be read."
        )

        return b""

    days_behind = Gauge(
        "trading_days_behind",
        "Trading days after the latest stored day that were final when the "
        "security's latest load ran.",
        ["symbol"],
        registry=registry,
    )
    for security in settings.securities + settings.indices:
        symbol = security.symbol
        # Without a stored day or a recorded load there is nothing to measure:
        if symbol in latest_days and symbol in latest_loads:
            behind = trading_days_behind(
                security.exchange,
                latest_days[symbol],
                latest_loads[symbol],
                settings.final_delay,
            )
            days_behind.labels(symbol).set(behind)
    # Before the first load there is nothing to measure; while the replay database
    # exists, the daily update pipeline is switched off on purpose.
    if latest_loads and not replaying:
        updates_missed = Gauge(
            "daily_updates_missed",
            "Scheduled daily updates after the latest load whose load limit passed.",
            registry=registry,
        )
        missed = daily_updates_missed(
            max(latest_loads.values()),
            now,
            settings.daily_update,
            settings.final_delay,
        )
        updates_missed.set(missed)

    return generate_latest(registry)


def report_drift_checks(settings: Settings, replaying: bool) -> bytes:
    """Report the latest finished drift check of each security and drift kind.

    The checks are read from MLflow's REST API within `DRIFT_READ_TIME_LIMIT` seconds,
    without retries. A security and drift kind that has no finished check gets no
    numbers. All drift numbers are left out when MLflow does not answer in time or
    answers with an error.

    @relation(REQ-MON-003, scope=function)

    Args:
        settings: Settings of this deployment.
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        The numbers in the text format Prometheus collects.
    """
    registry = CollectorRegistry()
    try:
        latest_checks = _read_latest_drift_checks(settings, replaying)
    except (httpx2.HTTPError, TimeoutError, json.JSONDecodeError):
        logger.exception("Drift checks left out: MLflow cannot be read.")

        return b""

    found = Gauge(
        "drift_found",
        "1 when the latest finished drift check of this security and drift kind found "
        "drift, otherwise 0.",
        ["symbol", "drift_kind"],
        registry=registry,
    )
    p_value = Gauge(
        "drift_p_value",
        "P-value of the latest finished drift check of this security and drift kind: "
        "the smaller it is, the stronger the evidence that the compared values come "
        "from different distributions.",
        ["symbol", "drift_kind"],
        registry=registry,
    )
    for (symbol, drift_kind), metrics in latest_checks.items():
        found.labels(symbol, drift_kind).set(metrics["drift_found"])
        p_value.labels(symbol, drift_kind).set(metrics["drift_p_value"])

    return generate_latest(registry)


def _read_latest_drift_checks(
    settings: Settings, replaying: bool
) -> dict[tuple[str, DriftKind], dict[str, float]]:
    """Read the metrics of each security's latest finished drift check from MLflow.

    It searches once per security and drift kind and asks for the latest finished run
    only, so each answer holds one run, however many runs MLflow holds. A single search
    over all runs would have to page through them until every pair is found.

    Args:
        settings: Settings of this deployment.
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        The metrics of the latest finished check of each pair that has one; empty when
        the drift checks experiment does not exist yet.
    """
    deadline = time.monotonic() + DRIFT_READ_TIME_LIMIT
    latest_checks: dict[tuple[str, DriftKind], dict[str, float]] = {}
    with httpx2.Client(base_url=settings.mlflow_tracking_uri) as client:
        response = _ask_mlflow(
            client,
            deadline,
            "GET",
            "/api/2.0/mlflow/experiments/get-by-name",
            params={"experiment_name": drift_checks_experiment_name(replaying)},
        )
        # MLflow answers 404 with this code when no check was ever recorded:
        if (
            response.status_code == 404
            and response.json()["error_code"] == "RESOURCE_DOES_NOT_EXIST"
        ):
            return latest_checks
        response.raise_for_status()
        experiment_id = response.json()["experiment"]["experiment_id"]
        for security, drift_kind in product(settings.securities, DriftKind):
            symbol = security.symbol
            response = _ask_mlflow(
                client,
                deadline,
                "POST",
                "/api/2.0/mlflow/runs/search",
                body={
                    "experiment_ids": [experiment_id],
                    "filter": (
                        f"tags.symbol = '{symbol}'"
                        f" and tags.drift_kind = '{drift_kind}'"
                        " and attributes.status = 'FINISHED'"
                    ),
                    "order_by": ["attributes.start_time DESC"],
                    "max_results": 1,
                },
            )
            response.raise_for_status()
            # When no run matches, MLflow leaves the "runs" key out of its answer:
            for run in response.json().get("runs", []):
                latest_checks[symbol, drift_kind] = {
                    metric["key"]: float(metric["value"])
                    for metric in run["data"]["metrics"]
                }

    return latest_checks


def _ask_mlflow(
    client: httpx2.Client,
    deadline: float,
    method: str,
    path: str,
    params: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> httpx2.Response:
    """Send one request to MLflow, allowing it the time left until the deadline."""
    time_left = deadline - time.monotonic()
    if time_left <= 0:
        raise TimeoutError("The time limit for the MLflow requests has run out")

    return client.request(method, path, params=params, json=body, timeout=time_left)


def trading_days_behind(
    exchange: str, latest_day: date, fetched_at: datetime, final_delay: timedelta
) -> int:
    """Count trading days after the latest stored day, final at the security's load.

    @relation(REQ-MON-003, scope=function)

    Args:
        exchange: MIC of the exchange the security trades on.
        latest_day: Latest stored day of the security.
        fetched_at: Time the latest load fetched the security, timezone-aware.
        final_delay: Time after the exchange's close from which a quote is final.

    Returns:
        The number of those trading days; 0 when none was final at the security's
        latest load.
    """
    behind = 0
    day = next_trading_day(exchange, latest_day)
    # The day was final when the load ran, so the load should have stored it.
    while is_final(exchange, day, fetched_at, final_delay):
        behind += 1
        day = next_trading_day(exchange, day)

    return behind


def daily_updates_missed(
    latest_load: datetime,
    now: datetime,
    daily_update: DailyUpdate,
    final_delay: timedelta,
) -> int:
    """Count scheduled daily updates after the latest load whose load limit has passed.

    @relation(REQ-MON-004, scope=function)

    Args:
        latest_load: Time of the latest recorded load, timezone-aware.
        now: Time to count up to, timezone-aware.
        daily_update: When the daily update pipeline loads.
        final_delay: Time after an exchange's close from which a quote is final; a
            load is due this long after start_after.

    Returns:
        The number of those updates; 0 when no update due after the latest load has
        passed its load limit.
    """
    missed = 0
    zone = daily_update.timezone
    day = latest_load.astimezone(zone).date()
    while day <= now.astimezone(zone).date():
        start = datetime.combine(day, daily_update.start_after, zone)
        due = start + final_delay
        scheduled = day.isoweekday() in daily_update.weekdays
        # Due after the latest load, and its load limit has passed without a load:
        if scheduled and latest_load < due <= now - daily_update.load_limit:
            missed += 1
        day += timedelta(days=1)

    return missed
