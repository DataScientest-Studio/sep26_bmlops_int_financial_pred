"""Integration tests of reading from the project database."""

from datetime import date

import pytest

from forecasting.db import read_latest_days
from forecasting.load import load_history
from tests.fakes import INDICES, SECURITIES, standard_source

pytestmark = pytest.mark.integration


def test_latest_stored_day_is_read_for_each_security(engine, settings):
    """Each security gets its own latest stored day."""
    load_history(
        engine,
        standard_source(),
        SECURITIES,
        INDICES,
        settings.final_delay,
        settings.history_start,
    )
    assert read_latest_days(engine) == {
        "TEST.US": date(2025, 12, 31),
        "TEST.DE": date(2025, 12, 30),
        "TEST.INDX": date(2025, 12, 31),
    }
