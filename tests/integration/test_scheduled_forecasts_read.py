"""Integration tests of reading scheduled forecasts from the project database."""

import pytest

from forecasting.db import read_scheduled_forecasts

pytestmark = pytest.mark.integration


def test_latest_scheduled_forecast_of_each_day_is_read_oldest_first(
    engine, store_forecast
):
    """REQ-MON-002: the latest scheduled forecast for each day is read, oldest first."""
    store_forecast(
        symbol="TEST.US",
        day="2026-03-04",
        requested_at="2026-03-03T22:00:00+00:00",
        scheduled=True,
        changes=[0.31, 0.32, 0.33, 0.34, 0.35],
    )
    store_forecast(
        symbol="TEST.US",
        day="2026-03-04",
        requested_at="2026-03-03T23:00:00+00:00",
        scheduled=True,
        changes=[0.41, 0.42, 0.43, 0.44, 0.45],
    )
    store_forecast(
        symbol="TEST.US",
        day="2026-03-02",
        requested_at="2026-03-01T22:00:00+00:00",
        scheduled=True,
        changes=[0.11, 0.12, 0.13, 0.14, 0.15],
    )
    store_forecast(
        symbol="TEST.US",
        day="2026-03-03",
        requested_at="2026-03-02T22:00:00+00:00",
        scheduled=True,
        changes=[0.21, 0.22, 0.23, 0.24, 0.25],
    )
    store_forecast(
        symbol="TEST.US",
        day="2026-03-03",
        requested_at="2026-03-03T08:00:00+00:00",
        scheduled=False,
        changes=[0.91, 0.92, 0.93, 0.94, 0.95],
    )
    store_forecast(
        symbol="TEST.US",
        day="2026-03-05",
        requested_at="2026-03-04T10:00:00+00:00",
        scheduled=False,
        changes=[0.81, 0.82, 0.83, 0.84, 0.85],
    )
    store_forecast(
        symbol="TEST.DE",
        day="2026-03-02",
        requested_at="2026-03-01T23:00:00+00:00",
        scheduled=True,
        changes=[0.61, 0.62, 0.63, 0.64, 0.65],
    )
    store_forecast(
        symbol="TEST.DE",
        day="2026-03-06",
        requested_at="2026-03-05T22:00:00+00:00",
        scheduled=True,
        changes=[0.71, 0.72, 0.73, 0.74, 0.75],
    )
    result = read_scheduled_forecasts(engine, "TEST.US")
    changes = result[["change_1", "change_2", "change_3", "change_4", "change_5"]]
    assert changes.to_numpy().tolist() == [
        [0.11, 0.12, 0.13, 0.14, 0.15],
        [0.21, 0.22, 0.23, 0.24, 0.25],
        [0.41, 0.42, 0.43, 0.44, 0.45],
    ]
