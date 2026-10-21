"""Acceptance tests of the automation requirements (black box)."""

import pandas as pd
import pytest

from forecasting.config import load_settings
from forecasting.db import connect
from forecasting.replay import replay_next_day
from tests.acceptance.tables import load_history_around_start, stored_table

pytestmark = pytest.mark.acceptance


def test_settings_load_when_started_from_another_folder(
    monkeypatch, tmp_path, example_settings
):
    """REQ-AUT-005: the settings list the project's securities from any folder."""
    monkeypatch.chdir(tmp_path)
    settings = load_settings()
    assert settings.securities == example_settings.securities


def test_first_replay_from_another_folder_fills_the_prices_up_to_the_start(
    monkeypatch, tmp_path, engine, settings, replay_url
):
    """REQ-AUT-005: from another folder, the first replay copies prices up to start."""
    load_history_around_start(engine, settings)
    monkeypatch.chdir(tmp_path)
    replay_next_day(engine, replay_url, settings.replay_start)
    replay_engine = connect(replay_url)
    replayed = stored_table(replay_engine, "prices")
    replay_engine.dispose()
    stored = stored_table(engine, "prices")
    expected = stored[stored["day"] <= settings.replay_start].reset_index(drop=True)
    pd.testing.assert_frame_equal(replayed, expected)
