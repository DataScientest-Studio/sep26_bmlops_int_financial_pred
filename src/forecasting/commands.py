"""Commands the Makefile runs: `python -m forecasting.commands <command>`.

The data service calls `run_load` and `run_replay`.
"""

import argparse
import os
import sys
from collections.abc import Callable
from datetime import date
from functools import partial

from sqlalchemy import Engine

from forecasting.config import Settings, load_settings
from forecasting.db import connect
from forecasting.eodhd import EodhdSource
from forecasting.failures import failure_reason
from forecasting.load import LoadReport, load_history
from forecasting.predict import predict
from forecasting.replay import replay_next_day, reset_replay
from forecasting.train import decide_training, train


def run_load() -> LoadReport:
    """Load prices, splits and dividends of the configured securities and indices.

    A security without stored prices is loaded from `HISTORY_START` on; otherwise
    each run fetches only the days from its latest stored one on.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)

    Returns:
        The report of the load: the numbers of new quotes stored, provisional quotes
        replaced, quotes, splits and dividends rejected, and trading days without a
        quote.
    """
    settings = load_settings()
    source = EodhdSource(os.environ["EODHD_API_KEY"])
    engine = connect(settings.database_url)
    report = load_history(
        engine,
        source,
        settings.securities,
        settings.indices,
        settings.final_delay,
        settings.history_start,
    )
    engine.dispose()

    return report


def load() -> None:
    """Run the load and print its report.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)

    Outputs:
        standard output: Three lines: the numbers of new quotes stored and provisional
            ones replaced, of quotes, splits and dividends rejected, and of trading
            days without a quote.
    """
    report = run_load()
    print(f"Stored {report.stored} new quotes, replaced {report.replaced} provisional.")
    print(f"Rejected {report.rejected} quotes, splits and dividends.")
    print(f"Missing: {report.missing} trading days without a quote.")


def run_replay() -> date | None:
    """Copy the next stored day into the replay database and return it.

    The first run fills the replay database up to `REPLAY_START`.

    @relation(REQ-DAT-003, scope=function)

    Returns:
        The day copied, or None when nothing is left to replay.
    """
    settings = load_settings()
    engine = connect(settings.database_url)
    day = replay_next_day(
        engine,
        settings.replay_database_url,
        settings.replay_start,
    )
    engine.dispose()

    return day


def replay() -> None:
    """Run the replay and print the day replayed, or that nothing is left to replay.

    @relation(REQ-DAT-003, scope=function)

    Outputs:
        standard output: One line: the day replayed, or that nothing is left to replay.
    """
    day = run_replay()
    if day is None:
        print("Nothing left to replay: the latest stored day is already replayed.")
    else:
        print(f"Replayed {day}.")


def replay_reset() -> None:
    """Delete the replay database and the replay runs and models in MLflow.

    The next replay starts over from `REPLAY_START`; training and forecasts return to
    the project database and its models.

    @relation(REQ-DAT-003, scope=function)
    """
    reset_replay(load_settings())


def _for_each_security(settings: Settings, action: Callable[[str], None]) -> None:
    """Run the action for each configured security, going on past a failed one.

    A failure is printed on the error output immediately, with the security's symbol
    and the reason, so an interrupted command still shows the failures so far.

    Args:
        settings: The settings holding the configured securities.
        action: What to do for one security, given its symbol.

    Raises:
        RuntimeError: If the action failed for any security; it is raised after the
            last security, and its message names each failed security with its reason.
    """
    failures = []
    for security in settings.securities:
        try:
            action(security.symbol)
        except Exception as error:
            failure = f"{security.symbol}: {failure_reason(error)}"
            print(failure, file=sys.stderr)
            failures.append(failure)
    if failures:
        raise RuntimeError("Failed for " + "; ".join(failures))


def _train_security(engine: Engine, settings: Settings, symbol: str) -> None:
    """Train and register a model for one security and print its scores."""
    # Training always runs here; decide_training first runs the feature drift check, and
    # the training run records that check's run id.
    decision = decide_training(engine, settings, symbol, only_when_needed=False)
    result = train(engine, settings, symbol, decision.drift_check_run_id)
    scores = result.evaluation
    status = "promoted" if result.promoted else "production kept"
    # Adjacent f-strings are joined without a space, so each continuation starts with
    # one. :.3% multiplies by 100 and adds %, so 0.01053 prints as 1.053%.
    print(
        f"{result.symbol}: model {result.model_version} ({status}), MAE"
        f" {scores.model.mae:.3%} (persistence {scores.persistence.mae:.3%},"
        f" mean change {scores.mean_change.mae:.3%}),"
        f" skill {scores.model.skill:+.3f}"
    )


def _predict_security(engine: Engine, settings: Settings, symbol: str) -> None:
    """Print the forecast of the next trading day for one security."""
    forecast = predict(engine, settings, symbol)
    # The + in :+.3% always shows the sign, as a move can go either way.
    print(
        f"{forecast.symbol} {forecast.day}: {forecast.change:+.3%} from close"
        f" {forecast.start_close:.2f} (model {forecast.model_version})"
    )


def train_models() -> None:
    """Train and register a model for each configured security and print its scores.

    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-MOD-002, scope=function)
    @relation(REQ-MON-001, scope=function)
    @relation(REQ-AUT-009, scope=function)

    A security that fails does not stop the others: its symbol and reason are printed
    on the error output immediately, and the command fails after the last security.

    Outputs:
        standard output: One line for each security that succeeded.
        standard error: A line for each failed security, printed immediately.

    Raises:
        RuntimeError: If training failed for any security; the message names each
            failed security with its reason.
    """
    settings = load_settings()
    engine = connect(settings.database_url)
    _for_each_security(settings, partial(_train_security, engine, settings))
    engine.dispose()


def predict_changes() -> None:
    """Print the forecast of the next trading day for each configured security.

    @relation(REQ-MOD-001, scope=function)
    @relation(REQ-AUT-009, scope=function)

    A security that fails does not stop the others: its symbol and reason are printed
    on the error output immediately, and the command fails after the last security.

    Outputs:
        standard output: One line for each security that succeeded.
        standard error: A line for each failed security, printed immediately.

    Raises:
        RuntimeError: If the forecast failed for any security; the message names each
            failed security with its reason.
    """
    settings = load_settings()
    engine = connect(settings.database_url)
    _for_each_security(settings, partial(_predict_security, engine, settings))
    engine.dispose()


COMMANDS = {
    "load": load,
    "replay": replay,
    "replay-reset": replay_reset,
    "train": train_models,
    "predict": predict_changes,
}


def main() -> None:
    """Run the command named on the command line.

    @relation(REQ-AUT-009, scope=function)

    Command:
        python -m forecasting.commands <command>

    Args:
        command: One of load, replay, replay-reset, train and predict; the Makefile
            passes it.

    Outputs:
        standard output: What the command reports; for train and predict, one line for
            each security that succeeded, even when another fails.
        standard error: The reason when the command fails, never a traceback; for train
            and predict, a security is named on its own line as soon as it fails;
            argparse's usage message when the command is missing or unknown.

    Exit codes:
        0: The command succeeded.
        1: The command failed.
        2: The command is missing or unknown.
    """
    parser = argparse.ArgumentParser(prog="python -m forecasting.commands")
    parser.add_argument("command", choices=COMMANDS)
    command = COMMANDS[parser.parse_args().command]
    try:
        command()
    except Exception as error:
        sys.exit(failure_reason(error))


if __name__ == "__main__":
    main()
