"""Integration tests of the numbers the API reports at `/metrics`."""

from datetime import UTC, datetime
from operator import itemgetter
from typing import Any

import pytest
from mlflow import MlflowClient
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import make_url, text

from forecasting.api.dependencies import get_engine
from forecasting.db import connect, create_database
from forecasting.drift_checks import DRIFT_CHECKS_EXPERIMENT_NAME, DriftKind
from forecasting.load import load_history
from tests.fakes import INDICES, SECURITIES, standard_source

pytestmark = pytest.mark.integration

# A local port nothing listens on, so connecting to the database or to MLflow fails at
# once.
CLOSED_PORT = 1

OLDER = datetime(2026, 1, 1, tzinfo=UTC)
NEWER = datetime(2026, 1, 2, tzinfo=UTC)


def _values_by_label(metrics_text: str, name: str, *labels: str) -> dict[Any, float]:
    """Return the values under one name in the `/metrics` text, keyed by label values.

    One label gives its value as key; several labels give a tuple of their values.
    """
    return {
        itemgetter(*labels)(sample.labels): sample.value
        for family in text_string_to_metric_families(metrics_text)
        for sample in family.samples
        if sample.name == name
    }


def _record_drift_check(
    client: MlflowClient,
    experiment_id: str,
    symbol: str,
    drift_kind: DriftKind,
    started: datetime,
    p_value: float,
    drift_found: int,
    status: str,
) -> None:
    """Record one drift check run, started at `started`, ended with `status`."""
    run = client.create_run(
        experiment_id,
        start_time=int(started.timestamp() * 1000),
        tags={"symbol": symbol, "drift_kind": drift_kind.value},
    )
    client.log_metric(run.info.run_id, "drift_p_value", p_value)
    client.log_metric(run.info.run_id, "drift_found", drift_found)
    client.set_terminated(run.info.run_id, status)


def _values(metrics_text: str, name: str) -> list[float]:
    """Return the values under one name in the `/metrics` text."""
    return [
        sample.value
        for family in text_string_to_metric_families(metrics_text)
        for sample in family.samples
        if sample.name == name
    ]


def test_metrics_count_a_request(client):
    """A request to the API is counted once under its route."""
    client.post("/predict", json={"symbol": "OTHER.US"})
    response = client.get("/metrics")
    assert response.status_code == 200
    counted = _values_by_label(response.text, "http_requests_total", "handler")
    assert counted == {"/predict": 1.0}


def test_metrics_without_database_keep_the_request_count(
    client, settings, change_settings
):
    """While the database cannot be read, requests are still reported."""
    url = make_url(settings.database_url).set(port=CLOSED_PORT)
    unreachable = connect(url.render_as_string(hide_password=False))
    replay_url = make_url(settings.replay_database_url).set(port=CLOSED_PORT)
    change_settings(
        replay_database_url=replay_url.render_as_string(hide_password=False)
    )
    client.app.dependency_overrides[get_engine] = lambda: unreachable
    client.post("/predict", json={"symbol": "OTHER.US"})
    response = client.get("/metrics")
    assert response.status_code == 200
    counted = _values_by_label(response.text, "http_requests_total", "handler")
    assert counted == {"/predict": 1.0}
    assert _values_by_label(response.text, "trading_days_behind", "symbol") == {}


def test_metrics_measure_trading_days_behind_at_the_latest_load(
    client, engine, settings
):
    """Trading days behind count at the latest load, also one storing nothing."""
    source = standard_source()
    load_history(
        engine,
        source,
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    source.fetched_at = datetime.fromisoformat("2026-01-02T22:00:00+00:00")
    load_history(
        engine,
        source,
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    response = client.get("/metrics")
    assert response.status_code == 200
    assert _values_by_label(response.text, "trading_days_behind", "symbol") == {
        "TEST.US": 1.0,
        "TEST.DE": 1.0,
        "TEST.INDX": 1.0,
    }


def test_metrics_without_a_recorded_load_report_no_trading_days_behind(
    client, engine, settings
):
    """A security without a recorded load gets no number of trading days behind."""
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE loads"))
    response = client.get("/metrics")
    assert response.status_code == 200
    assert _values_by_label(response.text, "trading_days_behind", "symbol") == {}


def test_metrics_after_a_load_just_now_count_no_missed_daily_update(
    client, engine, settings
):
    """A load recorded just now leaves no scheduled daily update missed."""
    source = standard_source()
    source.fetched_at = datetime.now(UTC)
    load_history(
        engine,
        source,
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    response = client.get("/metrics")
    assert response.status_code == 200
    assert _values(response.text, "daily_updates_missed") == [0.0]


def test_metrics_while_the_replay_database_exists_report_no_missed_daily_updates(
    client, engine, settings
):
    """While the replay database exists, missed daily updates are left out."""
    source = standard_source()
    source.fetched_at = datetime.now(UTC)
    load_history(
        engine,
        source,
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    create_database(settings.replay_database_url)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert _values(response.text, "daily_updates_missed") == []


def test_metrics_report_the_latest_finished_drift_check_of_each_security_and_kind(
    client, change_settings, mlflow_server_url
):
    """Drift numbers are those of the latest finished check, read from MLflow."""
    change_settings(mlflow_tracking_uri=mlflow_server_url)
    mlflow = MlflowClient(tracking_uri=mlflow_server_url)
    experiment_id = mlflow.create_experiment(DRIFT_CHECKS_EXPERIMENT_NAME)
    feature, prediction = DriftKind.FEATURE, DriftKind.PREDICTION
    _record_drift_check(
        mlflow, experiment_id, "TEST.US", feature, OLDER, 0.01, 1, "FINISHED"
    )
    _record_drift_check(
        mlflow, experiment_id, "TEST.US", feature, NEWER, 0.4, 0, "FINISHED"
    )
    _record_drift_check(
        mlflow, experiment_id, "TEST.DE", feature, OLDER, 0.02, 1, "FINISHED"
    )
    _record_drift_check(
        mlflow, experiment_id, "TEST.US", prediction, OLDER, 0.3, 0, "FINISHED"
    )
    _record_drift_check(
        mlflow, experiment_id, "TEST.US", prediction, NEWER, 0.005, 1, "FAILED"
    )
    response = client.get("/metrics")
    assert response.status_code == 200
    labels = ("symbol", "drift_kind")
    assert _values_by_label(response.text, "drift_found", *labels) == {
        ("TEST.US", feature.value): 0.0,
        ("TEST.DE", feature.value): 1.0,
        ("TEST.US", prediction.value): 0.0,
    }
    assert _values_by_label(response.text, "drift_p_value", *labels) == {
        ("TEST.US", feature.value): 0.4,
        ("TEST.DE", feature.value): 0.02,
        ("TEST.US", prediction.value): 0.3,
    }


def test_metrics_without_mlflow_report_no_drift_checks(client, change_settings):
    """While MLflow cannot be read, the drift numbers are left out."""
    change_settings(mlflow_tracking_uri=f"http://127.0.0.1:{CLOSED_PORT}")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert _values(response.text, "drift_found") == []
    assert _values(response.text, "drift_p_value") == []
