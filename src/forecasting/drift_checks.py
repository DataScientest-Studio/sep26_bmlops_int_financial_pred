"""Drift checks: whether recent values differ in distribution from earlier ones."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Any

import mlflow
import pandas as pd
from evidently import Report
from evidently.core.report import Snapshot
from evidently.metrics import ValueDrift
from mlflow import MlflowClient

from forecasting.config import SHORTEST_DRIFT_WINDOW, Settings
from forecasting.features import build_features
from forecasting.replay import REPLAY_PREFIX

DRIFT_CHECKS_EXPERIMENT_NAME = "drift-checks"
REPLAY_DRIFT_CHECKS_EXPERIMENT_NAME = f"{REPLAY_PREFIX}{DRIFT_CHECKS_EXPERIMENT_NAME}"
# Name of the run parameter in which a drift check records the latest stored trading day
# it saw; the next prediction drift check is due `prediction_drift_check_interval_days`
# stored trading days after it.
LATEST_DAY_CHECKED = "latest_day_checked"


class DriftKind(StrEnum):
    """Which values a drift check compares: daily changes or forecasts.

    Attributes:
        FEATURE: The daily price changes.
        PREDICTION: The model's forecasts.
    """

    FEATURE = "feature"
    PREDICTION = "prediction"


class FeatureDriftCheckStatus(StrEnum):
    """Whether the feature drift check of a training request ran, and if not, why.

    @relation(REQ-MON-001, scope=class)
    @relation(REQ-MON-006, scope=class)

    Attributes:
        COMPLETED: The check ran and was recorded in MLflow.
        SKIPPED_NO_RECORDED_TRAINING: The security has no recorded training.
        SKIPPED_TOO_FEW_REFERENCE_DAYS: Fewer than `SHORTEST_DRIFT_WINDOW` daily
            changes are stored before the check's window.
    """

    COMPLETED = "completed"
    SKIPPED_NO_RECORDED_TRAINING = "skipped: no recorded training"
    SKIPPED_TOO_FEW_REFERENCE_DAYS = "skipped: too few reference days"


class PredictionDriftCheckReason(StrEnum):
    """Why a prediction drift check of a security runs, or why not.

    @relation(REQ-MON-002, scope=class)

    Attributes:
        NO_EARLIER_CHECK: The security has no earlier prediction drift check.
        CHECK_INTERVAL_REACHED: Enough stored trading days lie after the latest check.
        NOT_DUE: The latest check is too recent.
        TOO_FEW_SCHEDULED_FORECASTS: Fewer days than `drift_window_days` have a
            scheduled forecast.
    """

    NO_EARLIER_CHECK = "no earlier check"
    CHECK_INTERVAL_REACHED = "check interval reached"
    NOT_DUE = "not due"
    TOO_FEW_SCHEDULED_FORECASTS = "too few scheduled forecasts"

    @property
    def check_runs(self) -> bool:
        """Tell whether the check runs for this reason.

        Returns:
            True when the check runs for this reason.
        """
        return self in {
            PredictionDriftCheckReason.NO_EARLIER_CHECK,
            PredictionDriftCheckReason.CHECK_INTERVAL_REACHED,
        }


@dataclass(frozen=True)
class DriftTestResult:
    """Outcome of one drift test.

    Attributes:
        p_value: P-value of the two-sample Kolmogorov-Smirnov test, 0 to 1: the smaller
            it is, the stronger the evidence that the recent and the reference values
            come from different distributions.
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
            every stored trading day before the recent ones.
        recent: Values of the latest days, of the same kind as `reference`.
        values_name: Name of the values in the report, for example "daily_change".
        p_value_threshold: Drift is found when the p-value is at or below it, 0.001 to
            0.1.

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
        p_value: P-value of the check's drift test, 0 to 1.
        drift_found: True when `p_value` is at or below the configured threshold.
    """

    run_id: str
    p_value: float
    drift_found: bool


def drift_checks_experiment_name(replaying: bool) -> str:
    """Return the name of the MLflow experiment drift checks are recorded in.

    @relation(REQ-DAT-003, scope=function)

    Args:
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        The experiment's name.
    """
    prefix = REPLAY_PREFIX if replaying else ""

    return f"{prefix}{DRIFT_CHECKS_EXPERIMENT_NAME}"


def check_feature_drift(
    settings: Settings,
    symbol: str,
    prices: pd.DataFrame,
    replaying: bool,
) -> DriftCheckResult | None:
    """Test whether a security's latest daily changes differ from all earlier ones.

    @relation(REQ-MON-001, scope=function)
    @relation(REQ-MON-006, scope=function)

    The daily changes of the latest `drift_window_days` stored trading days are compared
    with the daily changes of every stored trading day before them. The check is
    recorded as its own run in MLflow: the report as JSON, and as HTML when drift is
    found. Fewer than `SHORTEST_DRIFT_WINDOW` earlier daily changes are too few to test
    against: then nothing is tested or recorded.

    Args:
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        prices: The security's prices with a final close, oldest first, corrected for
            splits.
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        The id of the check's run, its p-value and whether drift is found; None when
        the check did not run for too few earlier daily changes.
    """
    # pct_change divides each close by the close before it, minus 1: the daily change.
    # The first day has no day before it, so its change is missing.
    daily_changes = prices["close"].pct_change()
    window_days = settings.drift_window_days
    reference = daily_changes.iloc[:-window_days].dropna()
    if len(reference) < SHORTEST_DRIFT_WINDOW:
        return None
    recent = daily_changes.iloc[-window_days:]
    test = run_drift_test(
        reference, recent, "daily_change", settings.drift_p_value_threshold
    )
    # The reference ends on the day before the window starts.
    reference_last_day = prices["day"].iloc[-window_days - 1]
    latest_day_checked = prices["day"].iloc[-1]
    check = _record_drift_check(
        settings,
        symbol,
        DriftKind.FEATURE,
        test,
        latest_day_checked,
        reference_last_day,
        replaying,
    )

    return check


def check_prediction_drift(
    settings: Settings,
    symbol: str,
    model: Any,
    prices: pd.DataFrame,
    scheduled_forecasts: pd.DataFrame,
    replaying: bool,
) -> DriftCheckResult:
    """Test whether a model's latest forecasts differ from its earlier ones.

    @relation(REQ-MON-002, scope=function)

    The model forecasts again from the stored inputs of the latest `drift_window_days`
    scheduled forecasts, and from the inputs of every stored trading day with complete
    inputs before the input day of the first of those forecasts; the two sets of
    forecasts are compared, so no input day is in both. The check is recorded as its own
    run in MLflow: the report as JSON, and as HTML when drift is found.

    Args:
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        model: The security's production model.
        prices: The security's prices with a final close, oldest first, corrected for
            splits.
        scheduled_forecasts: Day and inputs of the latest scheduled forecast of each
            day, oldest first, as from `forecasting.db.read_scheduled_forecasts`.
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        The id of the check's run, its p-value and whether drift is found.
    """
    features = build_features(prices)
    # The recent forecasts come from the same model and the stored inputs of the latest
    # scheduled forecasts, with the columns in the order the model learned them.
    window = scheduled_forecasts.tail(settings.drift_window_days)
    recent = pd.Series(model.predict(window[features.columns]))
    # A forecast for a day takes the latest stored day before it as input. The
    # reference is the model's forecasts from the stored days before the window's first
    # input day, built exactly as in training. A row is usable when every input is
    # present; the first days lack the history for them.
    days = prices["day"]
    first_input_day = days[days < window["day"].iloc[0]].max()
    reference_days = features.notna().all(axis=1) & (days < first_input_day)
    reference = pd.Series(model.predict(features[reference_days]))
    test = run_drift_test(
        reference, recent, "forecast", settings.drift_p_value_threshold
    )
    # The reference's last forecast uses the inputs of the stored day before
    # first_input_day, so it is for first_input_day.
    reference_last_day = first_input_day
    latest_day_checked = days.iloc[-1]
    check = _record_drift_check(
        settings,
        symbol,
        DriftKind.PREDICTION,
        test,
        latest_day_checked,
        reference_last_day,
        replaying,
    )

    return check


def find_latest_prediction_drift_check(
    settings: Settings, symbol: str, replaying: bool
) -> date | None:
    """Return the latest trading day a security's latest prediction drift check saw.

    @relation(REQ-MON-002, scope=function)

    Args:
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        That day, or None when the security has no finished prediction drift check.
    """
    client = MlflowClient(tracking_uri=settings.mlflow_tracking_uri)
    experiment = client.get_experiment_by_name(drift_checks_experiment_name(replaying))
    # The experiment does not exist yet, so nothing was ever checked.
    if experiment is None:
        return None
    runs = client.search_runs(
        [experiment.experiment_id],
        filter_string=(
            f"tags.symbol = '{symbol}' and tags.drift_kind = '{DriftKind.PREDICTION}'"
            " and attributes.status = 'FINISHED'"
        ),
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )
    if not runs:
        return None

    return date.fromisoformat(runs[0].data.params[LATEST_DAY_CHECKED])


def _record_drift_check(
    settings: Settings,
    symbol: str,
    drift_kind: DriftKind,
    test: DriftTestResult,
    latest_day_checked: date,
    reference_last_day: date,
    replaying: bool,
) -> DriftCheckResult:
    """Record a drift check as its own run in MLflow and return its outcome.

    Args:
        settings: Settings of this deployment.
        symbol: Ticker of the security.
        drift_kind: Which values the check compared.
        test: Outcome of the check's drift test.
        latest_day_checked: Latest stored trading day the check saw.
        reference_last_day: Last stored trading day the reference covers.
        replaying: Whether the replay database exists; replay checks are recorded in
            their own experiment.

    Returns:
        The id of the check's run, its p-value and whether drift is found.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    # The experiment is named in start_run, not only set: MLflow keeps the active
    # experiment for the whole process, and the API runs requests in several threads.
    experiment = mlflow.set_experiment(drift_checks_experiment_name(replaying))
    tags = {"symbol": symbol, "drift_kind": drift_kind}
    with mlflow.start_run(experiment_id=experiment.experiment_id, tags=tags) as run:
        mlflow.log_params(
            {
                "drift_window_days": settings.drift_window_days,
                LATEST_DAY_CHECKED: latest_day_checked,
                "reference_last_day": reference_last_day,
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
