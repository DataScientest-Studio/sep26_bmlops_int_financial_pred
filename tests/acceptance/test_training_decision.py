"""Acceptance tests of the training decision (black box over HTTP)."""

from collections.abc import Sequence
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from mlflow import MlflowClient
from mlflow.entities import Run

from forecasting.config import Settings
from forecasting.load import load_history
from tests.acceptance.tables import drift_checks, model_versions, run_of
from tests.fakes import SECURITIES, FakeSource, history_after, history_from_changes

pytestmark = pytest.mark.acceptance

SECURITY = SECURITIES[0]
# Ten daily changes that sum to 0, and the same changes ten times as large.
CALM = (0.01, -0.01, 0.005, -0.005, 0.02, -0.02, 0.0, 0.015, -0.015, 0.0)
VOLATILE = tuple(change * 10 for change in CALM)
# The smallest drift window, and the p-value at or below which a check finds drift.
DRIFT_SETTINGS = {"drift_window_days": 20, "drift_p_value_threshold": 0.01}


def _store(engine, settings: Settings, history: pd.DataFrame) -> None:
    """Store the days of one history for the first test security."""
    source = FakeSource({SECURITY.symbol: history})
    load_history(
        engine, source, (SECURITY,), (), settings.final_delay, settings.history_start
    )


def _store_first_year(engine, settings: Settings) -> date:
    """Store a calm year for the first test security; return its last day."""
    history = history_from_changes(SECURITY.exchange, "2024-01-01", "2024-12-31", CALM)
    _store(engine, settings, history)

    return history["day"].iloc[-1]


def _store_days_after(
    engine, settings: Settings, last_day: date, count: int, changes: Sequence[float]
) -> date:
    """Store `count` days after `last_day`; return the last of them."""
    history = history_after(SECURITY.exchange, last_day, count, changes)
    _store(engine, settings, history)

    return history["day"].iloc[-1]


def _artifact_names(settings: Settings, run: Run) -> set[str]:
    """Read the names of the artifacts a run holds, straight from MLflow."""
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)

    return {artifact.path for artifact in client.list_artifacts(run.info.run_id)}


def _request(client: TestClient, only_when_needed: bool) -> Response:
    """Send a training request for the first test security."""
    body = {"symbol": SECURITY.symbol, "only_when_needed": only_when_needed}

    return client.post("/training", json=body)


def test_unmarked_request_always_trains(client, engine, settings):
    """REQ-MOD-006: an unmarked request trains; REQ-MON-001: it records the check."""
    _store_first_year(engine, settings)
    first = client.post("/training", json={"symbol": SECURITY.symbol})
    second = client.post("/training", json={"symbol": SECURITY.symbol})
    assert first.status_code == 200
    assert first.json()["trained"] is True
    assert first.json()["training_decision_reason"] == "training requested"
    assert second.status_code == 200
    assert second.json()["trained"] is True
    assert second.json()["training_decision_reason"] == "training requested"
    assert len(model_versions(settings, SECURITY.symbol)) == 2
    checks = drift_checks(settings, SECURITY.symbol)
    assert len(checks) == 1
    assert _artifact_names(settings, checks[0]) == {"drift_report.json"}
    assert "drift_p_value" in checks[0].data.metrics
    trained = run_of(settings, SECURITY.symbol, second.json()["model_version"])
    assert trained.data.tags["drift_check_run_id"] == checks[0].info.run_id


def test_only_when_needed_trains_a_security_without_recorded_training(
    client, engine, settings
):
    """REQ-MOD-006: a marked request trains a security that was never trained."""
    _store_first_year(engine, settings)
    response = _request(client, only_when_needed=True)
    assert response.status_code == 200
    assert response.json()["trained"] is True
    assert response.json()["training_decision_reason"] == "no recorded training"
    assert response.json()["feature_drift_p_value"] is None


def test_only_when_needed_trains_once_the_retraining_interval_is_reached(
    client, engine, settings, change_settings
):
    """REQ-MOD-006: a marked request trains once the retraining interval is reached."""
    change_settings(retraining_interval_days=5, **DRIFT_SETTINGS)
    last_day = _store_first_year(engine, settings)
    client.post("/training", json={"symbol": SECURITY.symbol})
    last_day = _store_days_after(engine, settings, last_day, 4, CALM)
    before = _request(client, only_when_needed=True)
    _store_days_after(engine, settings, last_day, 1, CALM)
    reached = _request(client, only_when_needed=True)
    assert before.status_code == 200
    assert before.json()["trained"] is False
    assert before.json()["training_decision_reason"] == "not needed"
    assert before.json()["model_version"] is None
    assert reached.status_code == 200
    assert reached.json()["trained"] is True
    assert reached.json()["training_decision_reason"] == "retraining interval reached"


def test_only_when_needed_trains_when_drift_is_found(
    client, engine, settings, change_settings
):
    """REQ-MOD-006, REQ-MON-001: a marked request trains when the check finds drift."""
    change_settings(retraining_interval_days=250, **DRIFT_SETTINGS)
    last_day = _store_first_year(engine, settings)
    client.post("/training", json={"symbol": SECURITY.symbol})
    _store_days_after(engine, settings, last_day, 20, VOLATILE)
    response = _request(client, only_when_needed=True)
    assert response.status_code == 200
    assert response.json()["trained"] is True
    assert response.json()["training_decision_reason"] == "feature drift found"
    checks = drift_checks(settings, SECURITY.symbol)
    assert _artifact_names(settings, checks[0]) == {
        "drift_report.html",
        "drift_report.json",
    }
