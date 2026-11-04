"""Numbers the API reports to Prometheus."""

import logging
from datetime import UTC, date, datetime, timedelta

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
from forecasting.load import is_final
from forecasting.trading_calendar import next_trading_day

logger = logging.getLogger(__name__)

# Upper bounds, in seconds, of the steps response times are sorted into; they reach
# from a quick prediction up to a training run.
RESPONSE_TIME_STEPS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)


def add_metrics(app: FastAPI) -> None:
    """Count the API's requests; report them and the data's freshness at `/metrics`.

    Each application keeps its request numbers in a registry of its own, so
    applications never share counts.

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
        freshness = report_freshness(engine, settings, datetime.now(UTC))
        numbers = generate_latest(registry) + freshness

        return Response(numbers, media_type=CONTENT_TYPE_LATEST)


def report_freshness(engine: Engine, settings: Settings, now: datetime) -> bytes:
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

    Returns:
        The numbers in the text format Prometheus collects.
    """
    registry = CollectorRegistry()
    try:
        latest_days = read_latest_days(engine)
        latest_loads = read_latest_loads(engine)
        replay_database_exists = database_exists(settings.replay_database_url)
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
    if latest_loads and not replay_database_exists:
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
