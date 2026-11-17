"""Acceptance tests of the feature drift check's reference (black box over HTTP)."""

from datetime import date

import pytest

from tests.acceptance.tables import SECURITY, drift_checks, store
from tests.fakes import CALM, ELEVATED, history_after

pytestmark = pytest.mark.acceptance


def test_check_runs_with_twenty_earlier_changes(
    client, engine, settings, change_settings
):
    """REQ-MON-006: a check with 20 earlier daily changes runs and is recorded."""
    change_settings(drift_window_days=50, evaluation_days=1)
    store(
        engine,
        settings,
        history_after(SECURITY.exchange, date(2024, 1, 1), 71, CALM),
    )
    client.post("/training", json={"symbol": SECURITY.symbol})
    response = client.post("/training", json={"symbol": SECURITY.symbol})
    runs = drift_checks(settings, SECURITY.symbol)
    assert response.status_code == 200
    assert response.json()["feature_drift_check_status"] == "completed"
    assert isinstance(response.json()["feature_drift_p_value"], float)
    assert len(runs) == 1


def test_check_is_skipped_with_nineteen_earlier_changes(
    client, engine, settings, change_settings
):
    """REQ-MON-006: a check with 19 earlier daily changes does not run."""
    change_settings(drift_window_days=50, evaluation_days=1)
    store(
        engine,
        settings,
        history_after(SECURITY.exchange, date(2024, 1, 1), 70, CALM),
    )
    client.post("/training", json={"symbol": SECURITY.symbol})
    response = client.post("/training", json={"symbol": SECURITY.symbol})
    runs = drift_checks(settings, SECURITY.symbol)
    assert response.status_code == 200
    assert (
        response.json()["feature_drift_check_status"]
        == "skipped: too few reference days"
    )
    assert response.json()["feature_drift_p_value"] is None
    assert runs == []


def test_feature_drift_found_when_only_the_earliest_days_differ(
    client, engine, settings, change_settings
):
    """REQ-MON-001: the window is compared with all earlier stored days."""
    change_settings(
        drift_window_days=20, drift_p_value_threshold=0.05, evaluation_days=1
    )
    store(
        engine,
        settings,
        history_after(
            SECURITY.exchange, date(2024, 1, 1), 121, ELEVATED * 8 + CALM * 4
        ),
    )
    client.post("/training", json={"symbol": SECURITY.symbol})
    response = client.post("/training", json={"symbol": SECURITY.symbol})
    runs = drift_checks(settings, SECURITY.symbol)
    assert response.status_code == 200
    assert len(runs) == 1
    assert runs[0].data.metrics["drift_found"] == 1.0
    assert runs[0].data.params["reference_last_day"] == "2024-05-24"
