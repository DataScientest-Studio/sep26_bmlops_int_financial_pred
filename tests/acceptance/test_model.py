"""Acceptance tests of the model requirements (black box)."""

import pandas as pd
import pytest
from mlflow import MlflowClient
from mlflow.sklearn import load_model

from forecasting.datasets import dataset_version
from forecasting.db import read_prices
from forecasting.evaluate import evaluate
from forecasting.features import build_features, build_target
from forecasting.load import load_history
from forecasting.predict import predict
from forecasting.replay import replay_next_day, reset_replay
from forecasting.trading_calendar import next_trading_day
from forecasting.train import train
from tests.fakes import SECURITIES, FakeSource, price_history, standard_source

pytestmark = pytest.mark.acceptance


def test_target_is_next_day_close_to_close_change():
    """REQ-MOD-001: a day's target is the relative change to the next close."""
    prices = price_history("XNYS", "2026-10-05", "2026-10-07", seed=1)
    prices["close"] = [100.0, 110.0, 99.0]
    target = build_target(prices)
    assert target.iloc[0] == pytest.approx(0.10)
    assert target.iloc[1] == pytest.approx(-0.10)
    assert pd.isna(target.iloc[2])


def test_evaluation_scores_model_and_both_baselines_on_same_days():
    """REQ-MOD-002: persistence and mean change are scored next to the model."""
    actual = pd.Series([0.02, -0.01, 0.01])
    predicted = pd.Series([0.01, 0.01, 0.01])
    training_target = pd.Series([0.0, 0.01])
    result = evaluate(actual, predicted, training_target)
    assert result.days == 3
    assert result.persistence.mae == pytest.approx(0.04 / 3)
    assert result.mean_change.mae == pytest.approx(0.035 / 3)
    assert result.model.mae == pytest.approx(0.01)


def test_features_of_a_day_ignore_later_prices():
    """REQ-MOD-003: changing later prices leaves earlier features unchanged."""
    prices = price_history("XNYS", "2025-01-01", "2025-06-30", seed=3)
    cutoff = 80
    altered = prices.copy()
    altered.loc[cutoff + 1 :, ["open", "high", "low", "close"]] *= 1.5
    altered.loc[cutoff + 1 :, "volume"] *= 3
    pd.testing.assert_frame_equal(
        build_features(prices).iloc[: cutoff + 1],
        build_features(altered).iloc[: cutoff + 1],
    )


def test_training_evaluates_on_days_after_the_training_period(engine, settings):
    """REQ-MOD-003: evaluation days are later than every training day."""
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    result = train(engine, settings, SECURITIES[0].symbol)
    assert result.evaluation_start > result.training_end
    assert result.evaluation.days > 0


def test_training_records_parameters_metrics_versions_and_model(engine, settings):
    """REQ-MOD-004, REQ-DAT-006: run logs params, metrics, dataset/code ids, model."""
    symbol = SECURITIES[0].symbol
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    expected_dataset_version = dataset_version(
        settings, symbol, read_prices(engine, symbol)
    )
    result = train(engine, settings, symbol)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    version = client.get_model_version(f"forecast-{symbol}", result.model_version)
    assert version.run_id is not None
    run = client.get_run(version.run_id)
    assert run.data.params["dataset_version"] == expected_dataset_version
    assert run.data.params["code_version"] == settings.code_version
    assert int(run.data.params["evaluation_days"]) == settings.evaluation_days
    assert run.data.metrics["model_mae"] == pytest.approx(result.evaluation.model.mae)
    assert run.data.metrics["persistence_mae"] == pytest.approx(
        result.evaluation.persistence.mae
    )
    assert run.data.metrics["mean_change_mae"] == pytest.approx(
        result.evaluation.mean_change.mae
    )
    loaded = load_model(f"models:/forecast-{symbol}/{result.model_version}")
    assert loaded is not None


def test_first_trained_model_becomes_production(engine, settings):
    """REQ-MOD-005: the first model trained for a security becomes production."""
    symbol = SECURITIES[0].symbol
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    first = train(engine, settings, symbol)
    assert first.promoted is True
    assert predict(engine, settings, symbol).model_version == first.model_version


def test_model_that_is_not_better_keeps_current_production_model(engine, settings):
    """REQ-MOD-005: a model that does not beat production leaves production in place."""
    symbol = SECURITIES[0].symbol
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    first = train(engine, settings, symbol)
    second = train(engine, settings, symbol)
    assert second.model_version != first.model_version
    assert second.promoted is False
    assert predict(engine, settings, symbol).model_version == first.model_version


def test_better_model_replaces_production_model(engine, settings):
    """REQ-MOD-005: a model with lower evaluation MAE becomes the production model."""
    security = SECURITIES[0]
    first_year = price_history(security.exchange, "2024-01-01", "2024-12-31", seed=1)
    load_history(
        engine,
        FakeSource({security.symbol: first_year}),
        (security,),
        (),
        settings.final_delay,
        settings.history_start,
    )
    first = train(engine, settings, security.symbol)
    second_year = price_history(security.exchange, "2025-01-01", "2025-12-31", seed=2)
    start_close = float(first_year["close"].iloc[-1])
    for row in range(len(second_year)):
        second_year.loc[row, "close"] = start_close * (1.02 ** (row + 1))
    load_history(
        engine,
        FakeSource({security.symbol: second_year}),
        (security,),
        (),
        settings.final_delay,
        settings.history_start,
    )
    second = train(engine, settings, security.symbol)
    assert second.model_version != first.model_version
    assert second.promoted is True
    assert predict(engine, settings, security.symbol).model_version == (
        second.model_version
    )


def test_replay_switches_to_replay_database_and_models_until_reset(engine, settings):
    """REQ-DAT-003, REQ-MOD-005: replay uses replay DB/models; reset restores own."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2026-06-30", seed=1)
    load_history(
        engine,
        FakeSource({security.symbol: history}),
        (security,),
        (),
        settings.final_delay,
        settings.history_start,
    )
    own_model = train(engine, settings, security.symbol)
    replayed_day = replay_next_day(
        engine, settings.replay_database_url, settings.replay_start
    )
    assert replayed_day is not None
    replay_model = train(engine, settings, security.symbol)
    replay_forecast = predict(engine, settings, security.symbol)
    assert replay_forecast.day == next_trading_day(security.exchange, replayed_day)
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    assert client.get_model_version(
        f"replay-forecast-{security.symbol}", replay_model.model_version
    )
    reset_replay(settings)
    restored_forecast = predict(engine, settings, security.symbol)
    latest_own_day = history["day"].iloc[-1]
    assert restored_forecast.day == next_trading_day(security.exchange, latest_own_day)
    assert restored_forecast.model_version == own_model.model_version
    assert client.search_registered_models(filter_string="name LIKE 'replay-%'") == []
