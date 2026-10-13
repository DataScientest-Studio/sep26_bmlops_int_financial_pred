"""Commands the Makefile runs: `python -m forecasting.commands <command>`."""

import argparse
import os

from forecasting.config import load_settings
from forecasting.db import connect
from forecasting.eodhd import EodhdSource
from forecasting.load import load_history


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


COMMANDS = {"load": load}


def main() -> None:
    """Run the command named on the command line."""
    parser = argparse.ArgumentParser(prog="python -m forecasting.commands")
    parser.add_argument("command", choices=COMMANDS)
    COMMANDS[parser.parse_args().command]()


if __name__ == "__main__":
    main()
