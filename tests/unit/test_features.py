"""Unit tests of the correction of prices and volumes for splits."""

from datetime import date

import pandas as pd

from forecasting.features import correct_for_splits


def _prices(
    days: list[date], closes: list[float], volumes: list[float]
) -> pd.DataFrame:
    """Build stored prices of one security; open, high and low equal the close."""
    return pd.DataFrame(
        {
            "day": days,
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": volumes,
        }
    )


def _splits(days: list[date], ratios: list[float]) -> pd.DataFrame:
    """Build stored splits of one security."""
    return pd.DataFrame({"day": days, "ratio": ratios})


def test_days_before_two_splits_are_corrected_by_both_ratios():
    """Before a 2-for-1 and a 3-for-1 split, prices divided by 6, volumes times 6."""
    days = [date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8)]
    prices = _prices(days, [600.0, 300.0, 300.0, 100.0], [1, 1, 1, 1])
    splits = _splits([date(2026, 10, 6), date(2026, 10, 8)], [2.0, 3.0])
    expected = _prices(days, [100.0, 100.0, 100.0, 100.0], [6.0, 3.0, 3.0, 1.0])
    pd.testing.assert_frame_equal(correct_for_splits(prices, splits), expected)


def test_split_announced_for_a_later_day_changes_nothing():
    """A split whose day comes after the latest stored day is not applied."""
    days = [date(2026, 10, 5), date(2026, 10, 6)]
    prices = _prices(days, [100.0, 102.0], [1, 1])
    splits = _splits([date(2026, 10, 9)], [4.0])
    expected = _prices(days, [100.0, 102.0], [1.0, 1.0])
    pd.testing.assert_frame_equal(correct_for_splits(prices, splits), expected)
