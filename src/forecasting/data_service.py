"""Data service: runs the load and the replay for the scheduled pipelines."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI

from forecasting.commands import run_load, run_replay
from forecasting.config import load_settings
from forecasting.failures import report_failure
from forecasting.load import LoadReport


@asynccontextmanager
async def read_settings_at_start(app: FastAPI) -> AsyncIterator[None]:
    """Read the settings at start, so a refused setting stops the start.

    @relation(REQ-AUT-003, scope=function)
    @relation(REQ-AUT-007, scope=function)

    Args:
        app: The application being started; not read.
    """
    load_settings()
    yield


app = FastAPI(
    title="Financial forecasting data service",
    lifespan=read_settings_at_start,
)
app.add_exception_handler(Exception, report_failure)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the service is running.

    @relation(REQ-AUT-003, scope=function)

    Returns:
        The status "ok".
    """
    return {"status": "ok"}


@app.post("/load")
def load() -> LoadReport:
    """Run the load and answer with its report.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)

    Returns:
        The load's report.
    """
    return run_load()


@app.post("/replay")
def replay() -> dict[str, date | None]:
    """Copy the next stored day into the replay database and answer with it.

    @relation(REQ-DAT-003, scope=function)

    Returns:
        The replayed day under "day", or none when nothing is left to replay.
    """
    return {"day": run_replay()}
