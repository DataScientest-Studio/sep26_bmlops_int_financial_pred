"""Acceptance tests of the API requirements (black box over HTTP)."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from mlflow import MlflowClient

from forecasting.config import Security, Settings
from forecasting.load import load_history
from forecasting.trading_calendar import next_trading_day, session_close
from forecasting.train import EXPERIMENT_NAME, PRODUCTION_ALIAS
from tests.acceptance.tables import run_of, stored_table
from tests.fakes import (
    INDICES,
    SECURITIES,
    FakeSource,
    price_history,
    standard_source,
)

pytestmark = pytest.mark.acceptance

# What a run records, with a different value in each place so no two can be swapped.
RESULT_METRICS = {
    "model_mae": 0.012,
    "model_skill": 0.2,
    "model_directional_accuracy": 0.55,
    "persistence_mae": 0.015,
    "persistence_skill": 0.0,
    "persistence_directional_accuracy": 0.5,
    "mean_change_mae": 0.014,
    "mean_change_skill": 0.0667,
    "mean_change_directional_accuracy": 0.52,
}
# Evaluation days of the production version, and of a later version that is not.
EVALUATION_DAYS = 30
OTHER_EVALUATION_DAYS = 60
RESULT_BODY = {
    "symbol": "TEST.US",
    "model_version": "1",
    "evaluation_days": EVALUATION_DAYS,
    "model": {"mae": 0.012, "skill": 0.2, "directional_accuracy": 0.55},
    "persistence": {"mae": 0.015, "skill": 0.0, "directional_accuracy": 0.5},
    "mean_change": {"mae": 0.014, "skill": 0.0667, "directional_accuracy": 0.52},
    "mean_change_forecast": None,
}


def _seed_model_version(
    settings: Settings,
    symbol: str,
    evaluation_days: int,
    metrics: dict[str, float],
    production: bool = True,
) -> None:
    """Register a new model version of a security with a run that recorded results.

    Args:
        settings: Settings whose MLflow location receives the version.
        symbol: Ticker of the security.
        evaluation_days: Evaluation days the run records.
        metrics: Metrics the run records.
        production: Whether the version becomes the production model.
    """
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    name = f"forecast-{symbol}"
    experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
    assert experiment is not None
    run = client.create_run(experiment.experiment_id)
    assert run.info.artifact_uri is not None
    client.log_param(run.info.run_id, "evaluation_days", evaluation_days)
    for key, value in metrics.items():
        client.log_metric(run.info.run_id, key, value)
    if not client.search_registered_models(filter_string=f"name = '{name}'"):
        client.create_registered_model(name)
    version = client.create_model_version(
        name, source=run.info.artifact_uri, run_id=run.info.run_id
    )
    if production:
        client.set_registered_model_alias(name, PRODUCTION_ALIAS, version.version)


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
    assert body["model_version"] == "1"
    assert body["promoted"] is True
    assert body["evaluation_days"] > 0


def test_failed_training_answers_with_its_reason(
    client, engine, settings, change_settings
):
    """REQ-SVC-002: a training that fails answers 500 with a detail."""
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    change_settings(evaluation_days=10_000)
    failing = TestClient(client.app, raise_server_exceptions=False)
    response = failing.post("/training", json={"symbol": SECURITIES[0].symbol})
    assert response.status_code == 500
    assert set(response.json()) == {"detail"}


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


def test_securities_list_names_every_configured_security(client, engine, settings):
    """REQ-SVC-005: every configured security is listed, whatever prices are stored."""
    load_history(
        engine,
        standard_source(),
        (),
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    response = client.get("/securities")
    assert response.status_code == 200
    assert sorted(response.json()) == sorted(s.symbol for s in SECURITIES)


def test_history_is_latest_days_corrected_for_splits_with_provisional_close(
    client, engine, settings
):
    """REQ-SVC-006: latest days, split-corrected, latest close provisional."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-23", "2025-12-31", seed=1)
    # As traded: 2:1 split on the third day, a dividend on the fifth.
    history["close"] = [200.0, 202.0, 101.0, 102.0, 103.0, 104.5]
    history["open"] = history["close"]
    history["high"] = history["close"] * 1.01
    history["low"] = history["close"] * 0.99
    days = history["day"]
    splits = pd.DataFrame({"day": [days.iloc[2]], "ratio": [2.0]})
    dividends = pd.DataFrame(
        {"day": [days.iloc[4]], "amount": [1.0], "currency": "USD"}
    )
    # The fetch falls an hour before the latest day's close counts as final.
    final_from = session_close(security.exchange, days.iloc[-1]) + settings.final_delay
    source = FakeSource(
        {security.symbol: history},
        final_from - timedelta(hours=1),
        {security.symbol: splits},
        {security.symbol: dividends},
    )
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    response = client.get(f"/securities/{security.symbol}/history?days=5")
    assert response.status_code == 200
    expected = [101.0, 101.0, 102.0, 103.0, 104.5]
    assert response.json() == [
        {"day": day.isoformat(), "close": close}
        for day, close in zip(days.iloc[1:], expected)
    ]


def test_history_is_all_stored_days_when_fewer_than_asked(client, engine, settings):
    """REQ-SVC-006: all stored days are returned where fewer than asked are stored."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-12-23", "2025-12-30", seed=1)
    source = FakeSource({security.symbol: history})
    load_history(
        engine, source, (security,), (), settings.final_delay, settings.history_start
    )
    response = client.get(f"/securities/{security.symbol}/history?days=10")
    assert response.status_code == 200
    assert response.json() == [
        {"day": day.isoformat(), "close": pytest.approx(close)}
        for day, close in zip(history["day"], history["close"])
    ]


@pytest.mark.parametrize(
    "path",
    ["/securities/NOSUCH.US/history?days=3", "/securities/NOSUCH.US/model"],
    ids=["history", "model"],
)
def test_symbol_of_no_configured_security_is_refused_with_prices_and_model(
    client, engine, settings, path
):
    """REQ-SVC-006, REQ-SVC-007: an unknown symbol gets 404 though data is stored."""
    stranger = Security("NOSUCH.US", "XNYS")
    source = FakeSource(
        {
            stranger.symbol: price_history(
                stranger.exchange, "2025-01-01", "2025-12-31", seed=1
            )
        }
    )
    load_history(
        engine, source, (stranger,), (), settings.final_delay, settings.history_start
    )
    _seed_model_version(settings, stranger.symbol, EVALUATION_DAYS, RESULT_METRICS)
    response = client.get(path)
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/securities/TEST.DE/model", None),
        ("POST", "/predict", {"symbol": "TEST.DE"}),
    ],
    ids=["model", "predict"],
)
def test_security_without_production_model_is_refused(
    client, engine, settings, method, path, body
):
    """REQ-SVC-007, REQ-SVC-001: a configured security without a model gets 404."""
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    response = client.request(method, path, json=body)
    assert response.status_code == 404


def test_model_results_are_those_of_the_production_version(client, settings):
    """REQ-SVC-007: version, evaluation days and scores of the production model."""
    forecast = {"mean_change_forecast": 0.0004}
    _seed_model_version(settings, "TEST.US", EVALUATION_DAYS, RESULT_METRICS | forecast)
    other = {key: value + 1 for key, value in (RESULT_METRICS | forecast).items()}
    _seed_model_version(
        settings, "TEST.US", OTHER_EVALUATION_DAYS, other, production=False
    )
    response = client.get("/securities/TEST.US/model")
    assert response.status_code == 200
    assert response.json() == RESULT_BODY | forecast


def test_mean_change_forecast_is_null_when_the_run_did_not_record_it(client, settings):
    """REQ-SVC-007: the mean-change forecast is null where the run recorded none."""
    _seed_model_version(settings, "TEST.US", EVALUATION_DAYS, RESULT_METRICS)
    response = client.get("/securities/TEST.US/model")
    assert response.status_code == 200
    assert response.json() == RESULT_BODY


def test_model_results_after_training_are_those_the_training_run_recorded(
    client, engine, settings
):
    """REQ-SVC-007: the results of a freshly trained model match its training."""
    symbol = SECURITIES[0].symbol
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    trained = client.post("/training", json={"symbol": symbol}).json()
    response = client.get(f"/securities/{symbol}/model")
    assert response.status_code == 200
    body = response.json()
    run = run_of(settings, symbol, trained["model_version"])
    assert body["model_version"] == trained["model_version"]
    assert body["evaluation_days"] == trained["evaluation_days"]
    assert body["model"]["mae"] == pytest.approx(trained["model_mae"])
    assert body["persistence"]["mae"] == pytest.approx(trained["persistence_mae"])
    assert body["mean_change"]["mae"] == pytest.approx(trained["mean_change_mae"])
    assert body["mean_change_forecast"] == run.data.metrics["mean_change_forecast"]
