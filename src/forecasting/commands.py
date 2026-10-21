"""Commands the Makefile runs: `python -m forecasting.commands <command>`."""

import argparse
import os

from forecasting.config import load_settings
from forecasting.db import connect, drop_database
from forecasting.eodhd import EodhdSource
from forecasting.load import load_history
from forecasting.replay import replay_next_day


def load() -> None:
    """Load prices, splits and dividends of the configured securities and indices.

    A security without stored prices is loaded from `HISTORY_START` on; otherwise
    each run fetches only the days from its latest stored one on. Prints the load
    report.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)
    """
    settings = load_settings()
    source = EodhdSource(os.environ["EODHD_API_KEY"])
    report = load_history(
        connect(settings.database_url),
        source,
        settings.securities,
        settings.indices,
        settings.final_delay,
        settings.history_start,
    )
    print(f"Stored {report.stored} new quotes, replaced {report.replaced} provisional.")
    print(f"Rejected {report.rejected} quotes, splits and dividends.")
    print(f"Missing: {report.missing} trading days without a quote.")


def replay() -> None:
    """Copy the next stored day into the replay database and print it.

    The first run fills the replay database up to `REPLAY_START`. Prints the day
    replayed, or that nothing is left to replay.

    @relation(REQ-DAT-003, scope=function)
    """
    settings = load_settings()
    day = replay_next_day(
        connect(settings.database_url),
        settings.replay_database_url,
        settings.replay_start,
    )
    if day is None:
        print("Nothing left to replay: the latest stored day is already replayed.")
    else:
        print(f"Replayed {day}.")


def replay_reset() -> None:
    """Drop the replay database, so the next replay starts over from `REPLAY_START`.

    @relation(REQ-DAT-003, scope=function)
    """
    drop_database(load_settings().replay_database_url)


COMMANDS = {"load": load, "replay": replay, "replay-reset": replay_reset}


def main() -> None:
    """Run the command named on the command line."""
    parser = argparse.ArgumentParser(prog="python -m forecasting.commands")
    parser.add_argument("command", choices=COMMANDS)
    COMMANDS[parser.parse_args().command]()


if __name__ == "__main__":
    main()
