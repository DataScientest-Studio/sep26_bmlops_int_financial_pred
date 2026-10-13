"""Acceptance tests of the model requirements (black box)."""

import pandas as pd
import pytest

from forecasting.evaluate import evaluate
from forecasting.features import build_features, build_target
from forecasting.load import load_history
from forecasting.train import train
from tests.fakes import SECURITIES, price_history, standard_source

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
