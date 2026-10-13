"""Acceptance tests of the API requirements (black box over HTTP)."""

import exchange_calendars
import pytest

from forecasting.load import load_history
from tests.fakes import INDICES, SECURITIES, standard_source

pytestmark = pytest.mark.acceptance


def test_training_endpoint_trains_and_reports_outcome(client, engine, settings):
    """REQ-SVC-002: a training request returns the new model and its scores."""
    load_history(engine, standard_source(), SECURITIES, (), settings.final_delay)
    response = client.post("/training", json={"symbol": SECURITIES[0].symbol})
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == SECURITIES[0].symbol
    assert body["model_version"]
    assert body["evaluation_days"] > 0
    for key in ("model_mae", "persistence_mae", "mean_change_mae"):
        assert body[key] >= 0


def test_prediction_endpoint_forecasts_next_trading_day(client, engine, settings):
    """REQ-SVC-001, REQ-MOD-001: forecast for the next trading day, with model."""
    security = SECURITIES[0]
    source = standard_source()
    load_history(engine, source, SECURITIES, (), settings.final_delay)
    trained = client.post("/training", json={"symbol": security.symbol}).json()
    response = client.post("/predict", json={"symbol": security.symbol})
    assert response.status_code == 200
    body = response.json()
    latest = source.histories[security.symbol]["day"].iloc[-1]
    calendar = exchange_calendars.get_calendar(security.exchange)
    expected_day = calendar.next_session(latest).date()
    assert body["symbol"] == security.symbol
    assert body["day"] == expected_day.isoformat()
    assert isinstance(body["change"], float)
    assert body["model_version"] == trained["model_version"]


@pytest.mark.parametrize("endpoint", ["/training", "/predict"])
@pytest.mark.parametrize("symbol", [INDICES[0].symbol, "OTHER.US", "../x"])
def test_symbol_of_no_configured_security_is_refused(client, endpoint, symbol):
    """REQ-SVC-001, REQ-SVC-002: an index or unknown symbol gets 404."""
    response = client.post(endpoint, json={"symbol": symbol})
    assert response.status_code == 404
    assert symbol in response.json()["detail"]
