"""Drift checks between reference data and recent data."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DriftResult:
    """Outcome of a drift check.

    Attributes:
        drift_share: Fraction of the checked features flagged as drifted.
        drifted: True when `drift_share` exceeds the configured threshold.
    """

    drift_share: float
    drifted: bool


def check_drift(
    reference: pd.DataFrame, current: pd.DataFrame, threshold: float
) -> DriftResult:
    """Compare recent features with reference features.

    @relation(REQ-MON-001, scope=function)
    @relation(REQ-MON-002, scope=function)

    Args:
        reference: Features of the reference period.
        current: Features of the recent period, same columns.
        threshold: Drift share above which retraining is due.

    Returns:
        The drift share and whether it exceeds the threshold.
    """
    raise NotImplementedError
