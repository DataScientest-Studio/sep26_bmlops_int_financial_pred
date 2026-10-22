"""Acceptance tests of the API requirements (black box over HTTP)."""

from datetime import datetime

import pytest

from forecasting.load import load_history
from forecasting.trading_calendar import next_trading_day
from tests.fakes import INDICES, SECURITIES, standard_source

pytestmark = pytest.mark.acceptance


def test_training_endpoint_trains_and_reports_outcome(client, engine, settings):
    """REQ-SVC-002: a training request returns the new model and its scores."""
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    response = client.post("/training", json={"symbol": SECURITIES[0].symbol})
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == SECURITIES[0].symbol
    assert body["model_version"]
    assert body["promoted"] is True
    assert body["evaluation_days"] > 0


def test_prediction_endpoint_forecasts_next_trading_day(client, engine, settings):
    """REQ-SVC-001, REQ-MOD-001: next-day forecast, model, close it starts from."""
    security = SECURITIES[0]
    source = standard_source()
    load_history(
        engine, source, SECURITIES, (), settings.final_delay, settings.history_start
    )
    trained = client.post("/training", json={"symbol": security.symbol}).json()
    response = client.post("/predict", json={"symbol": security.symbol})
    assert response.status_code == 200
    body = response.json()
    latest = source.histories[security.symbol]["day"].iloc[-1]
    expected_day = next_trading_day(security.exchange, latest)
    assert body["symbol"] == security.symbol
    assert body["day"] == expected_day.isoformat()
    assert body["model_version"] == trained["model_version"]
    latest_close = source.histories[security.symbol]["close"].iloc[-1]
    assert body["start_close"] == pytest.approx(latest_close)
    assert datetime.fromisoformat(body["start_fetched_at"]) == source.fetched_at


@pytest.mark.parametrize("endpoint", ["/training", "/predict"])
@pytest.mark.parametrize("symbol", [INDICES[0].symbol, "OTHER.US"])
def test_symbol_of_no_configured_security_is_refused(client, endpoint, symbol):
    """REQ-SVC-001, REQ-SVC-002: an index or unknown symbol gets 404."""
    response = client.post(endpoint, json={"symbol": symbol})
    assert response.status_code == 404
