"""Model inputs and target built from the price history of one security."""

import pandas as pd

# How many daily changes, today's and the ones before it, go into the inputs.
CHANGE_DAYS = 5
# Lengths in trading days of the windows the volatility is measured over.
VOLATILITY_WINDOWS = (5, 20)


def build_features(prices: pd.DataFrame) -> pd.DataFrame:
    """Build the model inputs for each trading day.

    The features of a day use only prices up to and including that day: the
    daily changes of the last `CHANGE_DAYS` days, the volatility over each window
    in `VOLATILITY_WINDOWS` and the volume change.

    @relation(REQ-MOD-003, scope=function)

    Args:
        prices: Daily prices of one security, oldest first, as from
            `forecasting.db.read_prices`.

    Returns:
        One row per day, indexed like `prices`.
    """
    close = prices["close"]
    # Adding 1 keeps a day without trades from dividing by zero.
    volume = prices["volume"] + 1
    # The change into each day from the day before. shift(1) pulls every close down
    # one row, so each row sees the previous close; the first row has none.
    #
    #   day | close | close.shift(1) | change
    #   1   | 100   | NaN            | NaN
    #   2   | 110   | 100            |  0.10
    #   3   | 99    | 110            | -0.10
    #   4   | 99    | 99             |  0.00
    change = close / close.shift(1) - 1
    # An empty table with the same row labels as prices, filled column by column.
    features = pd.DataFrame(index=prices.index)
    # Today's change (change_1) and the ones of the days before it (change_2, ...).
    # A positive shift only looks back, so no later price reaches a day's inputs.
    #
    #   day | change | change_1 | change_2 = change.shift(1)
    #   2   |  0.10  |  0.10    | NaN
    #   3   | -0.10  | -0.10    |  0.10
    #   4   |  0.00  |  0.00    | -0.10
    for days_back in range(CHANGE_DAYS):
        features[f"change_{days_back + 1}"] = change.shift(days_back)
    # How strongly the price swung: the standard deviation of the daily changes over
    # the day and the window - 1 days before it; missing until the window is full.
    for window in VOLATILITY_WINDOWS:
        features[f"volatility_{window}"] = change.rolling(window).std()
    # The relative change of the traded volume against the day before.
    features["volume_change"] = volume / volume.shift(1) - 1

    return features


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
    close = prices["close"]

    # Returns the relative change to the next trading day's close, e.g. 0.02 for a
    # 2 % rise. Each row is one trading day, so shift(-1) pulls the next day's close
    # up one row and leaves the latest day missing.
    #
    #   day | close | close.shift(-1) | target (what we return)
    #   1   | 100   | 110             |  0.10
    #   2   | 110   | 99              | -0.10
    #   3   | 99    | NaN             | NaN
    return close.shift(-1) / close - 1
