"""Data service wiring, with load and replay replaced."""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from forecasting import data_service
from forecasting.load import LoadReport


def test_health_reports_running_service():
    """The started service answers its health check."""
    response = TestClient(data_service.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_load_answers_with_the_load_report(monkeypatch: pytest.MonkeyPatch):
    """A load answers with the report of the load it ran."""
    report = LoadReport(stored=3, replaced=1, rejected=0, missing=2)
    monkeypatch.setattr(data_service, "run_load", lambda: report)
    response = TestClient(data_service.app).post("/load")

    assert response.status_code == 200
    assert response.json() == {"stored": 3, "replaced": 1, "rejected": 0, "missing": 2}


def test_replay_answers_with_the_replayed_day(monkeypatch: pytest.MonkeyPatch):
    """A replay answers with the day it copied."""
    monkeypatch.setattr(data_service, "run_replay", lambda: date(2026, 6, 2))
    response = TestClient(data_service.app).post("/replay")

    assert response.status_code == 200
    assert response.json() == {"day": "2026-06-02"}


def test_replay_answers_none_when_nothing_is_left(monkeypatch: pytest.MonkeyPatch):
    """A replay with nothing left to copy answers with no day."""
    monkeypatch.setattr(data_service, "run_replay", lambda: None)
    response = TestClient(data_service.app).post("/replay")

    assert response.status_code == 200
    assert response.json() == {"day": None}


def test_failed_load_answers_with_its_reason(monkeypatch: pytest.MonkeyPatch):
    """A load that fails answers with the error's type and message."""

    def fail() -> LoadReport:
        raise RuntimeError("EODHD answered 401 for eod/TEST.US")

    monkeypatch.setattr(data_service, "run_load", fail)
    client = TestClient(data_service.app, raise_server_exceptions=False)
    response = client.post("/load")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "RuntimeError: EODHD answered 401 for eod/TEST.US"
    }
