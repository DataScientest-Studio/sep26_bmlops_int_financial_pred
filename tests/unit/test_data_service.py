"""Data service wiring."""

import pytest
from fastapi.testclient import TestClient

from forecasting import data_service


def test_health_reports_running_service():
    """The started service answers its health check."""
    response = TestClient(data_service.app).get("/health")

    assert response.status_code == 200


def test_data_service_refuses_to_start_with_a_refused_setting(
    monkeypatch: pytest.MonkeyPatch,
):
    """A setting the settings refuse stops the data service's start."""
    monkeypatch.setenv("HISTORY_START", "1979-12-31")

    with pytest.raises(ValueError), TestClient(data_service.app):
        pass
