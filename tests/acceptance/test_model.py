"""Acceptance tests of the model requirements (black box)."""

from datetime import date, timedelta

import pandas as pd
import pytest
from mlflow.sklearn import load_model

from forecasting.datasets import dataset_version
from forecasting.db import read_prices, read_splits
from forecasting.evaluate import evaluate
from forecasting.features import build_features, build_target, correct_for_splits
from forecasting.load import load_history
from forecasting.predict import predict
from forecasting.trading_calendar import session_close
from forecasting.train import train
from tests.acceptance.tables import run_of
from tests.fakes import SECURITIES, FakeSource, price_history, standard_source

pytestmark = pytest.mark.acceptance

# Factor of each day's close over the day before in a steadily rising year: 2% a day.
DAILY_RISE = 1.02


def test_target_is_next_day_close_to_close_change():
    """REQ-MOD-001: a day's target is the relative change to the next close."""
    prices = price_history("XNYS", "2026-10-05", "2026-10-07", seed=1)
    prices["close"] = [100.0, 110.0, 99.0]
    target = build_target(prices)
    assert target.iloc[0] == pytest.approx(0.10)
    assert target.iloc[1] == pytest.approx(-0.10)
    assert pd.isna(target.iloc[2])


def test_target_across_a_split_day_is_the_real_change():
    """REQ-MOD-001: closes corrected for splits give the real change across a split."""
    prices = price_history("XNYS", "2026-10-05", "2026-10-06", seed=1)
    prices["close"] = [100.0, 26.0]
    splits = pd.DataFrame({"day": [prices["day"].iloc[1]], "ratio": [4.0]})
    target = build_target(correct_for_splits(prices, splits))
    assert target.iloc[0] == pytest.approx(0.04)


def test_evaluation_scores_model_and_both_baselines_on_same_days():
    """REQ-MOD-002: persistence and mean change are scored next to the model."""
    actual = pd.Series([0.02, -0.01, 0.01])
    predicted = pd.Series([0.01, 0.01, 0.01])
    training_target = pd.Series([0.0, 0.01])
    result = evaluate(actual, predicted, training_target)
    assert result.days == 3
    assert vars(result.model) == pytest.approx(
        {"mae": 0.01, "skill": 0.25, "directional_accuracy": 2 / 3}
    )
    assert vars(result.persistence) == pytest.approx(
        {"mae": 0.04 / 3, "skill": 0.0, "directional_accuracy": 0.0}
    )
    assert vars(result.mean_change) == pytest.approx(
        {"mae": 0.035 / 3, "skill": 0.125, "directional_accuracy": 2 / 3}
    )


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
    """REQ-MOD-004: a run records params, metrics, dataset and code version, model."""
    symbol = SECURITIES[0].symbol
    splits = pd.DataFrame({"day": [date(2025, 6, 2)], "ratio": [2.0]})
    load_history(
        engine,
        standard_source(splits={symbol: splits}),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    # Every stored day is final, so training uses all of them, corrected for the split.
    trained_rows = correct_for_splits(
        read_prices(engine, symbol), read_splits(engine, symbol)
    )
    expected_dataset_version = dataset_version(settings, symbol, trained_rows)
    result = train(engine, settings, symbol)
    run = run_of(settings, symbol, result.model_version)
    assert run.data.params["dataset_version"] == expected_dataset_version
    assert run.data.params["code_version"] == settings.code_version
    assert run.data.params["evaluation_days"] == str(settings.evaluation_days)
    assert run.data.metrics["model_mae"] == pytest.approx(result.evaluation.model.mae)
    assert run.data.metrics["persistence_mae"] == pytest.approx(
        result.evaluation.persistence.mae
    )
    assert run.data.metrics["mean_change_mae"] == pytest.approx(
        result.evaluation.mean_change.mae
    )
    loaded = load_model(f"models:/forecast-{symbol}/{result.model_version}")
    assert loaded is not None


def test_training_records_whether_its_model_was_promoted(engine, settings):
    """REQ-MOD-004: a run records whether its model became the production model."""
    symbol = SECURITIES[0].symbol
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        (),
        settings.final_delay,
        settings.history_start,
    )
    # The first model always becomes production; the second, trained on the same days,
    # is no better, so production is kept.
    first = train(engine, settings, symbol)
    second = train(engine, settings, symbol)
    first_run = run_of(settings, symbol, first.model_version)
    second_run = run_of(settings, symbol, second.model_version)
    promoted = (first_run.data.tags["promoted"], second_run.data.tags["promoted"])
    assert promoted == ("true", "false")


def test_training_leaves_out_a_provisional_latest_day(engine, settings):
    """REQ-MOD-001: the model is trained on final closes only."""
    security = SECURITIES[0]
    history = price_history(security.exchange, "2025-01-01", "2025-12-31", seed=3)
    # The fetch falls an hour before the latest day's close counts as final, so that
    # day is provisional and every earlier day is final.
    final_from = session_close(security.exchange, history["day"].iloc[-1])
    final_from += settings.final_delay
    load_history(
        engine,
        FakeSource({security.symbol: history}, final_from - timedelta(hours=1)),
        (security,),
        (),
        settings.final_delay,
        settings.history_start,
    )
    stored = read_prices(engine, security.symbol)
    final_rows = correct_for_splits(
        stored.iloc[:-1], read_splits(engine, security.symbol)
    )
    expected_dataset_version = dataset_version(settings, security.symbol, final_rows)
    result = train(engine, settings, security.symbol)
    run = run_of(settings, security.symbol, result.model_version)
    assert run.data.params["dataset_version"] == expected_dataset_version


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
    # A second year that rises by DAILY_RISE every day: a model trained on it
    # forecasts its latest days far better than the first year's model.
    second_year = price_history(security.exchange, "2025-01-01", "2025-12-31", seed=2)
    start_close = float(first_year["close"].iloc[-1])
    for row in range(len(second_year)):
        second_year.loc[row, "close"] = start_close * (DAILY_RISE ** (row + 1))
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
