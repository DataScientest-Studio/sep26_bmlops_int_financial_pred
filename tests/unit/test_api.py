"""API wiring that works without database or model."""

from fastapi.testclient import TestClient

from forecasting.api.app import create_app


def test_health_reports_running_service():
    """REQ-AUT-003: the started service answers its health check."""
    response = TestClient(create_app()).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
