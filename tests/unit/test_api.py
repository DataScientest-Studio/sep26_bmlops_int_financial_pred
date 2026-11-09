"""API wiring that works without database or model."""

import pytest
from fastapi.testclient import TestClient

from forecasting.api.app import create_app
from forecasting.api.dependencies import get_settings


def test_health_reports_running_service():
    """The started service answers its health check."""
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200


def test_api_refuses_to_start_with_a_refused_setting(monkeypatch):
    """A setting the settings refuse stops the API's start."""
    monkeypatch.setenv("HISTORY_START", "1979-12-31")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError), TestClient(create_app()):
            pass
    finally:
        get_settings.cache_clear()
