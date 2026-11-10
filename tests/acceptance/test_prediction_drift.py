"""Acceptance tests of the prediction drift check (black box over HTTP)."""

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from mlflow import MlflowClient

from tests.acceptance.tables import (
    SECURITY,
    drift_checks,
    store,
    store_and_forecast_days,
    store_days_after,
    store_first_year,
)
from tests.fakes import CALM, VOLATILE, history_after, history_from_changes

pytestmark = pytest.mark.acceptance

# The smallest drift window.
WINDOW = 20
# A p-value threshold stricter than the configured one: only a shift of the latest
# days' forecasts counts as drift, not a mix with the calm days before them.
STRICT_P_VALUE_THRESHOLD = 0.001


def _train(client: TestClient) -> None:
    """Train the first test security."""
    client.post("/training", json={"symbol": SECURITY.symbol})


def _check(client: TestClient) -> Response:
    """Send a prediction drift check request for the first test security."""
    return client.post("/prediction-drift-check", json={"symbol": SECURITY.symbol})


def test_first_check_runs_when_there_is_no_earlier_check(
    client, engine, settings, change_settings
):
    """REQ-MON-002: a security with no earlier prediction drift check is checked."""
    change_settings(drift_window_days=WINDOW)
    last_day = store_first_year(engine, settings)
    _train(client)
    # The second training records a feature drift check, which is no earlier prediction
    # drift check.
    _train(client)
    calm = history_after(SECURITY.exchange, last_day, WINDOW, CALM)
    store_and_forecast_days(client, engine, settings, calm)
    response = _check(client)
    assert response.status_code == 200
    assert response.json()["checked"] is True
    assert response.json()["check_decision_reason"] == "no earlier check"


def test_a_security_with_too_few_days_of_scheduled_forecasts_is_not_checked(
    client, engine, settings, change_settings
):
    """REQ-MON-002: a security with too few scheduled forecast days is not checked."""
    change_settings(drift_window_days=WINDOW)
    last_day = store_first_year(engine, settings)
    _train(client)
    calm = history_after(SECURITY.exchange, last_day, WINDOW - 1, CALM)
    last_day = store_and_forecast_days(client, engine, settings, calm)
    store_days_after(engine, settings, last_day, 1, CALM)
    # An unscheduled forecast for the last day does not count.
    client.post("/predict", json={"symbol": SECURITY.symbol})
    response = _check(client)
    assert response.status_code == 200
    assert response.json()["checked"] is False
    assert response.json()["check_decision_reason"] == "too few scheduled forecasts"
    assert response.json()["prediction_drift_p_value"] is None
    assert response.json()["prediction_drift_found"] is None
    assert drift_checks(settings, SECURITY.symbol) == []


def test_a_check_runs_again_once_the_check_interval_is_reached(
    client, engine, settings, change_settings
):
    """REQ-MON-002: a security is checked again once the check interval is reached."""
    change_settings(drift_window_days=WINDOW, prediction_drift_check_interval_days=2)
    last_day = store_first_year(engine, settings)
    _train(client)
    calm = history_after(SECURITY.exchange, last_day, WINDOW, CALM)
    last_day = store_and_forecast_days(client, engine, settings, calm)
    _check(client)
    one_day = history_after(SECURITY.exchange, last_day, 1, CALM)
    last_day = store_and_forecast_days(client, engine, settings, one_day)
    before = _check(client)
    store_days_after(engine, settings, last_day, 1, CALM)
    reached = _check(client)
    assert before.status_code == 200
    assert before.json()["checked"] is False
    assert before.json()["check_decision_reason"] == "not due"
    assert reached.status_code == 200
    assert reached.json()["checked"] is True
    assert reached.json()["check_decision_reason"] == "check interval reached"


def test_drift_is_found_and_recorded_when_the_latest_forecasts_shift(
    client, engine, settings, change_settings, tmp_path
):
    """REQ-MON-002: a check over the latest window finds drift and records it."""
    change_settings(
        drift_window_days=WINDOW, drift_p_value_threshold=STRICT_P_VALUE_THRESHOLD
    )
    history = history_from_changes(SECURITY.exchange, "2024-01-01", "2025-03-31", CALM)
    year_end = date(2024, 12, 31)
    store(engine, settings, history[history["day"] <= year_end])
    _train(client)
    calm = history[history["day"] > year_end].head(WINDOW)
    last_day = store_and_forecast_days(client, engine, settings, calm)
    volatile = history_after(SECURITY.exchange, last_day, WINDOW, VOLATILE)
    store_and_forecast_days(client, engine, settings, volatile)
    response = _check(client)
    runs = drift_checks(settings, SECURITY.symbol)
    assert response.status_code == 200
    assert response.json()["prediction_drift_found"] is True
    assert len(runs) == 1
    assert (
        runs[0].data.metrics["drift_p_value"]
        == response.json()["prediction_drift_p_value"]
    )
    mlflow_client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    report = mlflow_client.download_artifacts(
        runs[0].info.run_id, "drift_report.json", str(tmp_path)
    )
    assert Path(report).exists()


def test_no_drift_is_found_when_the_latest_forecasts_stay_calm(
    client, engine, settings, change_settings
):
    """REQ-MON-002: a check over calm forecasts answers that no drift is found."""
    change_settings(
        drift_window_days=WINDOW, drift_p_value_threshold=STRICT_P_VALUE_THRESHOLD
    )
    history = history_from_changes(SECURITY.exchange, "2024-01-01", "2025-03-31", CALM)
    year_end = date(2024, 12, 31)
    store(engine, settings, history[history["day"] <= year_end])
    _train(client)
    calm = history[history["day"] > year_end].head(WINDOW)
    store_and_forecast_days(client, engine, settings, calm)
    response = _check(client)
    assert response.status_code == 200
    assert response.json()["prediction_drift_found"] is False
