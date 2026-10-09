"""Model inputs and target built from the price history of one security."""

import pandas as pd


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Build the model inputs for each trading day.

    The features of a day use only prices up to and including that day: the
    changes of the last 1–5 days, 5- and 20-day volatility and the volume change.

    @relation(REQ-MOD-003, scope=function)

    Args:
        prices: Daily prices of one security, oldest first, as from
            `forecasting.db.read_prices`.

    Returns:
        One row per day, indexed like `prices`.
    """
    raise NotImplementedError


def build_target(prices: pd.DataFrame) -> pd.Series:
    """Build the value the model predicts for each trading day.

    The target of a day is the relative close-to-close change from that day to
    the next trading day; it is missing for the latest day.

    @relation(REQ-MOD-001, scope=function)

    Args:
        prices: Daily prices of one security, oldest first.

    Returns:
        One value per day, indexed like `prices`.
    """
    raise NotImplementedError
