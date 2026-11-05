"""Model inputs and target built from the price history of one security."""

import pandas as pd

# How many daily changes, today's and the ones before it, go into the inputs.
CHANGE_DAYS = 5


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

    The features of a day use only prices up to and including that day: its own daily
    change and the ones of the `CHANGE_DAYS` - 1 days before it; some are missing on
    the first `CHANGE_DAYS` days.

    @relation(REQ-MOD-003, scope=function)

    Args:
        prices: Daily prices of one security, oldest first, corrected for splits by
            `correct_for_splits`.

    Returns:
        One row per day, indexed like `prices`.
    """
    # The relative change into each day from the day before; the first day has none.
    # pct_change() computes close / close.shift(1) - 1: shift(1) pulls every close
    # down one row, so each row sees the previous close.
    #
    #   day | close | close.shift(1) | change
    #   1   | 100   | NaN            | NaN
    #   2   | 110   | 100            |  0.10
    #   3   | 99    | 110            | -0.10
    change = prices["close"].pct_change()
    # An empty table with the same row labels as prices, filled column by column.
    features = pd.DataFrame(index=prices.index)
    # Today's change (change_1) and the ones of the days before it (change_2, ...).
    # A positive shift only looks back, so no later price reaches a day's inputs.
    #
    #   day | change | change_1 | change_2 = change.shift(1)
    #   2   |  0.10  |  0.10    | NaN
    #   3   | -0.10  | -0.10    |  0.10
    for days_back in range(CHANGE_DAYS):
        features[f"change_{days_back + 1}"] = change.shift(days_back)

    return features


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
    # The relative change to the next trading day's close, for example 0.02 for a 2%
    # rise. shift(-1) pulls each day's change up one row, onto the day before it; the
    # latest day has no next day.
    #
    #   day | close | pct_change() | target = pct_change().shift(-1)
    #   1   | 100   | NaN          |  0.10
    #   2   | 110   |  0.10        | -0.10
    #   3   | 99    | -0.10        | NaN
    return prices["close"].pct_change().shift(-1)
