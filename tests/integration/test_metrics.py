"""Integration tests of the numbers the API reports at `/metrics`."""

from datetime import UTC, datetime

import pytest
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import make_url, text

from forecasting.api.dependencies import get_engine
from forecasting.db import connect, create_database
from forecasting.load import load_history
from tests.fakes import INDICES, SECURITIES, standard_source

pytestmark = pytest.mark.integration

# A local port nothing listens on, so connecting to the database fails at once.
CLOSED_PORT = 1


def _values_by_label(metrics_text: str, name: str, label: str) -> dict[str, float]:
    """Return the values under one name in the `/metrics` text, keyed by one label."""
    return {
        sample.labels[label]: sample.value
        for family in text_string_to_metric_families(metrics_text)
        for sample in family.samples
        if sample.name == name
    }


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


def test_metrics_without_database_keep_the_request_count(client, settings):
    """While the database cannot be read, requests are still reported."""
    url = make_url(settings.database_url).set(port=CLOSED_PORT)
    unreachable = connect(url.render_as_string(hide_password=False))
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
