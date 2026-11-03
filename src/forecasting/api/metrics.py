"""Numbers the API reports to Prometheus."""

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Gauge,
    generate_latest,
)
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.exc import OperationalError

from forecasting.api.dependencies import EngineDep, SettingsDep
from forecasting.db import read_latest_days
from forecasting.load import is_final
from forecasting.trading_calendar import next_trading_day

logger = logging.getLogger(__name__)

# Upper bounds, in seconds, of the steps response times are sorted into; they reach
# from a quick prediction up to a training run.
RESPONSE_TIME_STEPS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60)


def add_metrics(app: FastAPI) -> None:
    """Count the API's requests; report them and the trading days behind at `/metrics`.

    Each application keeps its numbers in a registry of its own, so applications
    never share counts.

    @relation(REQ-MON-003, scope=function)

    Args:
        app: The API to measure.
    """
    registry = CollectorRegistry()
    days_behind = Gauge(
        "trading_days_behind",
        "Trading days after the latest stored day whose final price is available.",
        ["symbol"],
        registry=registry,
    )
    # The health check and Prometheus call these routes on a timer; counting them would
    # drown the requests of users.
    instrumentator = Instrumentator(
        excluded_handlers=["/health", "/metrics"],
        registry=registry,
    )
    instrumentator.instrument(app, latency_lowr_buckets=RESPONSE_TIME_STEPS)

    @app.get("/metrics", include_in_schema=False)
    def metrics(engine: EngineDep, settings: SettingsDep) -> Response:
        """Report the API's numbers in the text format Prometheus collects.

        While the database cannot be read, the trading days behind are left out and the
        request numbers are still reported.
        """
        try:
            latest_days = read_latest_days(engine)
        except OperationalError:
            logger.exception(
                "Trading days behind left out: the database cannot be read."
            )
            days_behind.clear()
        else:
            now = datetime.now(UTC)
            for security in settings.securities + settings.indices:
                if security.symbol in latest_days:
                    behind = trading_days_behind(
                        security.exchange,
                        latest_days[security.symbol],
                        now,
                        settings.final_delay,
                    )
                    days_behind.labels(security.symbol).set(behind)

        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


def trading_days_behind(
    exchange: str, latest_day: date, now: datetime, final_delay: timedelta
) -> int:
    """Count trading days after the latest stored day whose final price is available.

    @relation(REQ-MON-003, scope=function)

    Args:
        exchange: MIC of the exchange the security trades on.
        latest_day: Latest stored day of the security.
        now: Current time, timezone-aware.
        final_delay: Time after the exchange's close from which a quote is final.

    Returns:
        The number of those trading days; 0 when no such day has passed.
    """
    behind = 0
    day = next_trading_day(exchange, latest_day)
    # A price fetched now would be final, so that day's final price is available.
    while is_final(exchange, day, now, final_delay):
        behind += 1
        day = next_trading_day(exchange, day)

    return behind
