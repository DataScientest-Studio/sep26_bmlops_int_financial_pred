"""Contract tests of EODHD: how it delivers prices and splits, read through our client.

They call EODHD with the key in `.env` (`make contract`), so a change in what EODHD
delivers fails a test. A check the key cannot support (history that does not reach
back far enough, too few calls left today, a refused request) is skipped with its
reason.
"""

import os
from datetime import date, timedelta
from typing import Any

import httpx2
import pandas as pd
import pytest
from pydantic import SecretStr

from forecasting.db import PRICE_COLUMNS
from forecasting.eodhd import API_URL, EodhdSource
from forecasting.trading_calendar import CALENDAR_START, next_trading_day

APPLE = "AAPL.US"
APPLE_SPLIT_DAY = date(2020, 8, 31)
APPLE_SPLIT_RATIO = 4.0
# EODHD counts a request for the splits of a whole exchange as 100 calls:
BULK_CALLS = 100

pytestmark = pytest.mark.eodhd


def _get(api_key: SecretStr, path: str, **params: str) -> Any:
    """Send one request to EODHD; skip the test if EODHD refuses it for this key.

    The key stays hidden in every failure report and is unwrapped only here; the
    error message names the path only, never the URL, which carries the key.
    """
    query = {"api_token": api_key.get_secret_value(), "fmt": "json", **params}
    response = httpx2.get(f"{API_URL}/{path}", params=query, timeout=30)
    if response.status_code == 403:
        pytest.skip(f"EODHD refuses {path} for this key")
    if response.status_code != 200:
        pytest.fail(f"EODHD answered {response.status_code} for {path}")

    return response.json()


def _require_calls(api_key: SecretStr, calls: int) -> None:
    """Skip the test unless the key has that many calls left today."""
    account = _get(api_key, "user")
    left = account["dailyRateLimit"] - account["apiRequests"]
    if left < calls:
        pytest.skip(f"{calls} calls needed, {left} left today")


def _around(history: pd.DataFrame, day: date, days: int) -> pd.DataFrame:
    """Return the quotes from `days` calendar days before `day` to as many after.

    Skips the test if the history does not reach back that far.
    """
    first = day - timedelta(days=days)
    if history["day"].min() > first:
        pytest.skip(f"history does not reach back to {first}")
    in_window = (history["day"] >= first) & (history["day"] <= day + timedelta(days))

    return history[in_window]


@pytest.fixture(scope="module")
def api_key() -> SecretStr:
    """The member's own EODHD key, from `.env`, hidden in every report."""
    key = os.environ.get("EODHD_API_KEY", "")
    if not key:
        pytest.skip("EODHD_API_KEY is empty in .env")

    return SecretStr(key)


@pytest.fixture(scope="module")
def source(api_key: SecretStr) -> EodhdSource:
    """Our EODHD client."""
    return EodhdSource(api_key.get_secret_value())


@pytest.fixture(scope="module")
def apple_history(api_key: SecretStr, source: EodhdSource) -> pd.DataFrame:
    """Apple's daily price history, as far back as the key reaches."""
    # Apple's history and splits cost two calls:
    _require_calls(api_key, 2)

    return source.fetch_history(APPLE, CALENDAR_START)


def test_history_has_the_price_columns(apple_history):
    """Each quote carries the columns the database stores."""
    assert list(apple_history.columns) == PRICE_COLUMNS


def test_history_days_are_plain_dates(apple_history):
    """Days are plain dates, never a datetime or a pandas Timestamp."""
    assert all(type(day) is date for day in apple_history["day"])


def test_fetch_time_carries_a_timezone(apple_history):
    """The fetch time is timezone-aware."""
    assert apple_history["fetched_at"].iloc[0].tzinfo is not None


def test_split_ratio_is_new_shares_per_old_share(source, apple_history):
    """Apple's 4-for-1 split arrives as ratio 4.0 on its day."""
    # Skips if the key's history does not reach the split:
    _around(apple_history, APPLE_SPLIT_DAY, 14)
    splits = source.fetch_splits(APPLE).set_index("day")
    assert splits.loc[APPLE_SPLIT_DAY, "ratio"] == APPLE_SPLIT_RATIO


def test_split_day_is_the_day_the_price_changes(apple_history):
    """The close falls by the split's ratio on the split's listed day."""
    close = _around(apple_history, APPLE_SPLIT_DAY, 14).set_index("day")["close"]
    before = close[close.index < APPLE_SPLIT_DAY].iloc[-1]
    assert before / close[APPLE_SPLIT_DAY] == pytest.approx(APPLE_SPLIT_RATIO, rel=0.1)


def test_volumes_before_a_split_are_corrected_from_its_day(apple_history):
    """Volumes before a split are multiplied by its ratio, up to the day before it."""
    volume = _around(apple_history, APPLE_SPLIT_DAY, 14)["volume"]
    # Uncorrected, a day before the 4-for-1 split would show about a quarter of the
    # shares of the days after it, far below 0.4 of the median:
    assert (volume / volume.median()).between(0.4, 2.5).all()


def test_an_announced_split_is_listed_before_any_volume_holds_it(api_key, source):
    """A split for the next trading day is listed, yet the latest volume is as traded.

    The latest volume is compared with EODHD's live quote, which is never corrected.
    Only a split of at least 3-for-1 or 1-for-3 is used, so a corrected volume would
    differ from the live one by that factor.
    """
    _require_calls(api_key, BULK_CALLS + 10)
    split_day = next_trading_day("XNYS", date.today())
    params = {"type": "splits", "date": split_day.isoformat()}
    listed = _get(api_key, "eod-bulk-last-day/US", **params)
    for symbol in (f"{split['code']}.US" for split in listed):
        splits = source.fetch_splits(symbol).set_index("day")
        assert split_day in splits.index
        ratio = splits.loc[split_day, "ratio"]
        if ratio >= 3 or ratio <= 1 / 3:
            break
    else:
        pytest.skip(f"no US split of ratio 3 or more, or 1/3 or less, for {split_day}")
    recent = source.fetch_history(symbol, date.today() - timedelta(days=14))
    latest = recent["volume"].iloc[-1]
    live = _get(api_key, f"real-time/{symbol}")["volume"]
    assert 0.5 <= latest / live <= 2
