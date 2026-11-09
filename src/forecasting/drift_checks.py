"""Drift checks: whether recent values differ in distribution from earlier ones."""

from dataclasses import dataclass
from datetime import date

import mlflow
import pandas as pd
from evidently import Report
from evidently.core.report import Snapshot
from evidently.metrics import ValueDrift

from forecasting.config import Settings
from forecasting.replay import REPLAY_PREFIX

DRIFT_CHECKS_EXPERIMENT_NAME = "drift-checks"
REPLAY_DRIFT_CHECKS_EXPERIMENT_NAME = f"{REPLAY_PREFIX}{DRIFT_CHECKS_EXPERIMENT_NAME}"


@dataclass(frozen=True)
class DriftTestResult:
    """Outcome of one drift test.

    Attributes:
        p_value: P-value of the two-sample Kolmogorov-Smirnov test: the smaller it is,
            the less likely the recent and the reference values share one distribution.
        drift_found: True when `p_value` is at or below the threshold.
        report: Evidently's report of the test, to store as JSON or HTML.
    """

    p_value: float
    drift_found: bool
    report: Snapshot


def run_drift_test(
    reference: pd.Series,
    recent: pd.Series,
    values_name: str,
    p_value_threshold: float,
) -> DriftTestResult:
    """Test whether the recent values come from another distribution than the reference.

    @relation(REQ-MON-001, scope=function)
    @relation(REQ-MON-002, scope=function)

    Args:
        reference: Values of the reference period, for example the daily changes of
            every stored trading day up to a security's latest training.
        recent: Values of the latest days, of the same kind as `reference`.
        values_name: Name of the values in the report, for example "daily_change".
        p_value_threshold: Drift is found when the p-value is at or below it.

    Returns:
        The p-value, whether drift is found, and the report.
    """
    # The Kolmogorov-Smirnov test, named explicitly: for more than 1000 reference values
    # Evidently picks another test by default, which finds drift in almost every
    # comparison with a few dozen recent values.
    test = ValueDrift(column=values_name, method="ks", threshold=p_value_threshold)
    report = Report([test]).run(
        current_data=pd.DataFrame({values_name: recent}),
        reference_data=pd.DataFrame({values_name: reference}),
    )
    # The report holds one result per metric; ValueDrift's value is the p-value.
    p_value = float(report.dict()["metrics"][0]["value"])

    return DriftTestResult(
        p_value=p_value, drift_found=p_value <= p_value_threshold, report=report
    )


@dataclass(frozen=True)
class DriftCheckResult:
    """Outcome of one drift check, recorded as its own run in MLflow.

    Attributes:
        run_id: Id of the check's run in MLflow.
        p_value: P-value of the check's drift test.
        drift_found: True when `p_value` is at or below the configured threshold.
    """

    run_id: str
    p_value: float
    drift_found: bool


def drift_checks_experiment_name(replaying: bool) -> str:
    """Return the name of the MLflow experiment drift checks are recorded in.

    @relation(REQ-DAT-003, scope=function)
    """
    prefix = REPLAY_PREFIX if replaying else ""

    return f"{prefix}{DRIFT_CHECKS_EXPERIMENT_NAME}"


def check_feature_drift(
    settings: Settings,
    symbol: str,
    prices: pd.DataFrame,
    prices_until: date,
    replaying: bool,
) -> DriftCheckResult:
    """Test whether a security's latest daily changes drifted since its latest training.

    The daily changes of the latest `drift_window_days` stored trading days are compared
    with the daily changes of every day up to `prices_until`, the last day of the prices
    the latest training used. The check is recorded as its own run in MLflow: the report
    as JSON, and as HTML when drift is found.

    @relation(REQ-MON-001, scope=function)

    Args:
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        prices: The security's prices with a final close, oldest first, corrected for
            splits.
        prices_until: Last day of the prices the security's latest training used.
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        The id of the check's run, its p-value and whether drift is found.
    """
    # pct_change divides each close by the close before it, minus 1: the daily change.
    # The first day has no day before it, so its change is missing.
    daily_changes = prices["close"].pct_change()
    reference = daily_changes[prices["day"] <= prices_until].dropna()
    recent = daily_changes.iloc[-settings.drift_window_days :]
    test = run_drift_test(
        reference, recent, "daily_change", settings.drift_p_value_threshold
    )
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    # The experiment is named in start_run, not only set: MLflow keeps the active
    # experiment for the whole process, and the API trains in several threads.
    experiment = mlflow.set_experiment(drift_checks_experiment_name(replaying))
    tags = {"symbol": symbol, "drift_kind": "feature"}
    with mlflow.start_run(experiment_id=experiment.experiment_id, tags=tags) as run:
        mlflow.log_params(
            {
                "drift_window_days": settings.drift_window_days,
                "latest_day_checked": prices["day"].iloc[-1],
                "reference_last_day": prices_until,
            }
        )
        mlflow.log_metrics(
            {"drift_p_value": test.p_value, "drift_found": int(test.drift_found)}
        )
        mlflow.log_text(test.report.json(), "drift_report.json")
        # The HTML report is far larger than the JSON one, so it is kept only when drift
        # is found.
        if test.drift_found:
            mlflow.log_text(
                test.report.get_html_str(as_iframe=False), "drift_report.html"
            )

    return DriftCheckResult(
        run_id=run.info.run_id, p_value=test.p_value, drift_found=test.drift_found
    )
