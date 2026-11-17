"""Integration tests of reading scheduled forecasts from the project database."""

from datetime import date

import pytest

from forecasting.db import read_scheduled_forecasts
from tests.fakes import SECURITIES

pytestmark = pytest.mark.integration


def test_latest_scheduled_forecast_of_each_day_is_read_oldest_first(
    engine, store_forecast
):
    """The latest scheduled forecast of each day of a security is read, oldest first."""
    store_forecast(
        symbol=SECURITIES[0].symbol,
        day="2026-03-04",
        requested_at="2026-03-03T22:00:00+00:00",
        scheduled=True,
        changes=[0.31, 0.32, 0.33, 0.34, 0.35],
        change=0.3,
    )
    store_forecast(
        symbol=SECURITIES[0].symbol,
        day="2026-03-04",
        requested_at="2026-03-03T23:00:00+00:00",
        scheduled=True,
        changes=[0.41, 0.42, 0.43, 0.44, 0.45],
        change=0.4,
    )
    store_forecast(
        symbol=SECURITIES[0].symbol,
        day="2026-03-04",
        requested_at="2026-03-03T21:00:00+00:00",
        scheduled=True,
        changes=[0.51, 0.52, 0.53, 0.54, 0.55],
        change=0.5,
    )
    store_forecast(
        symbol=SECURITIES[0].symbol,
        day="2026-03-02",
        requested_at="2026-03-02T07:00:00+00:00",
        scheduled=True,
        changes=[0.11, 0.12, 0.13, 0.14, 0.15],
        change=0.1,
    )
    store_forecast(
        symbol=SECURITIES[0].symbol,
        day="2026-03-03",
        requested_at="2026-03-01T22:00:00+00:00",
        scheduled=True,
        changes=[0.21, 0.22, 0.23, 0.24, 0.25],
        change=0.2,
    )
    store_forecast(
        symbol=SECURITIES[0].symbol,
        day="2026-03-03",
        requested_at="2026-03-03T08:00:00+00:00",
        scheduled=False,
        changes=[0.91, 0.92, 0.93, 0.94, 0.95],
        change=0.9,
    )
    store_forecast(
        symbol=SECURITIES[0].symbol,
        day="2026-03-05",
        requested_at="2026-03-04T10:00:00+00:00",
        scheduled=False,
        changes=[0.81, 0.82, 0.83, 0.84, 0.85],
        change=0.8,
    )
    store_forecast(
        symbol=SECURITIES[1].symbol,
        day="2026-03-02",
        requested_at="2026-03-02T09:00:00+00:00",
        scheduled=True,
        changes=[0.61, 0.62, 0.63, 0.64, 0.65],
        change=0.6,
    )
    result = read_scheduled_forecasts(engine, SECURITIES[0].symbol)
    assert result.to_dict("records") == [
        {
            "day": date(2026, 3, 2),
            "change": 0.1,
            "change_1": 0.11,
            "change_2": 0.12,
            "change_3": 0.13,
            "change_4": 0.14,
            "change_5": 0.15,
        },
        {
            "day": date(2026, 3, 3),
            "change": 0.2,
            "change_1": 0.21,
            "change_2": 0.22,
            "change_3": 0.23,
            "change_4": 0.24,
            "change_5": 0.25,
        },
        {
            "day": date(2026, 3, 4),
            "change": 0.4,
            "change_1": 0.41,
            "change_2": 0.42,
            "change_3": 0.43,
            "change_4": 0.44,
            "change_5": 0.45,
        },
    ]
