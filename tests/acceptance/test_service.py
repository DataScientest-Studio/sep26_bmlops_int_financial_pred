"""Acceptance tests of the API requirements (black box over HTTP)."""

from datetime import UTC, datetime

import pandas as pd
import pytest

from forecasting.load import load_history
from forecasting.trading_calendar import next_trading_day
from tests.acceptance.tables import stored_table
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


def test_forecast_is_stored_with_features_and_request_time(client, engine, settings):
    """REQ-SVC-003: a forecast is stored with features, model version, request time."""
    security = SECURITIES[0]
    source = standard_source()
    history = source.histories[security.symbol]
    last_six = history.index[-6:]
    history.loc[last_six, "close"] = [100.0, 110.0, 99.0, 99.0, 108.9, 108.9]
    history.loc[last_six, "open"] = history.loc[last_six, "close"]
    history.loc[last_six, "high"] = history.loc[last_six, "close"] * 1.01
    history.loc[last_six, "low"] = history.loc[last_six, "close"] * 0.99
    load_history(
        engine, source, SECURITIES, (), settings.final_delay, settings.history_start
    )
    client.post("/training", json={"symbol": security.symbol})
    before = datetime.now(UTC)
    response = client.post("/predict", json={"symbol": security.symbol})
    after = datetime.now(UTC)
    assert response.status_code == 200
    body = response.json()
    stored = stored_table(engine, "predictions")
    assert len(stored) == 1
    row = stored.iloc[0]
    assert row["symbol"] == body["symbol"]
    assert pd.Timestamp(row["day"]) == pd.Timestamp(body["day"])
    assert row["model_version"] == body["model_version"]
    assert row["change"] == pytest.approx(body["change"])
    assert float(row["start_close"]) == pytest.approx(body["start_close"])
    assert row["start_fetched_at"] == datetime.fromisoformat(body["start_fetched_at"])
    assert row["change_1"] == pytest.approx(0.0)
    assert row["change_2"] == pytest.approx(0.10)
    assert row["change_3"] == pytest.approx(0.0)
    assert row["change_4"] == pytest.approx(-0.10)
    assert row["change_5"] == pytest.approx(0.10)
    assert before <= row["requested_at"] <= after


@pytest.mark.parametrize("endpoint", ["/training", "/predict"])
@pytest.mark.parametrize("symbol", [INDICES[0].symbol, "OTHER.US"])
def test_symbol_of_no_configured_security_is_refused(client, endpoint, symbol):
    """REQ-SVC-001, REQ-SVC-002: an index or unknown symbol gets 404."""
    response = client.post(endpoint, json={"symbol": symbol})
    assert response.status_code == 404
