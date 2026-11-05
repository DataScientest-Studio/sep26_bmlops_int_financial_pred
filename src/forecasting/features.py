"""Model inputs and target built from the price history of one security."""

import pandas as pd


def correct_for_splits(prices: pd.DataFrame, splits: pd.DataFrame) -> pd.DataFrame:
    """Express every day's prices and volume in the shares of the latest day.

    A split changes the number of shares, not the company's value: after a 4-for-1 split
    one old share is four new ones. Every price before a split is divided by its ratio
    and every volume multiplied by it, so a split day shows its real change.
    A split announced for a day after the latest one has not happened yet and is left
    out.

    @relation(REQ-MOD-001, scope=function)

    Args:
        prices: Daily prices of one security as stored, as from
            `forecasting.db.read_prices`.
        splits: Splits of the same security, as from `forecasting.db.read_splits`.

    Returns:
        The prices with open, high, low, close and volume corrected for every split up
        to the latest day.
    """
    # How many shares of the latest day one share of each day is worth: 1 since the
    # last split, and before a split, its ratio multiplied by the ratios of the later
    # splits that have happened.
    shares = pd.Series(1.0, index=prices.index)
    latest_day = prices["day"].max()
    for split in splits.to_dict("records"):
        # Only a split on or before the latest day has happened:
        if split["day"] <= latest_day:
            shares.loc[prices["day"] < split["day"]] *= split["ratio"]
    corrected = prices.copy()
    for column in ["open", "high", "low", "close"]:
        corrected[column] = prices[column] / shares
    corrected["volume"] = prices["volume"] * shares

    return corrected


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Build the model inputs for each trading day.

    The features of a day use only prices up to and including that day: the
    changes of the last 1–5 days, 5- and 20-day volatility and the volume change.

    @relation(REQ-MOD-003, scope=function)

    Args:
        prices: Daily prices of one security, oldest first, corrected for splits by
            `correct_for_splits`.

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
        prices: Daily prices of one security, oldest first, corrected for splits by
            `correct_for_splits`.

    Returns:
        One value per day, indexed like `prices`.
    """
    raise NotImplementedError
