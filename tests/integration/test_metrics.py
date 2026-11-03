"""Integration tests of the numbers the API reports at `/metrics`."""

import pytest
from prometheus_client.parser import text_string_to_metric_families
from sqlalchemy import make_url

from forecasting.api.dependencies import get_engine
from forecasting.db import connect

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
