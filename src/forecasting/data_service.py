"""Data service: runs the load and the replay for the scheduled pipelines."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from forecasting.commands import run_load, run_replay
from forecasting.config import load_settings
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
    title="Financial forecasting data service", lifespan=read_settings_at_start
)


@app.exception_handler(Exception)
def report_failure(request: Request, error: Exception) -> JSONResponse:
    """Answer a failed load or replay with its reason, so the pipeline can show it.

    The error still reaches the service's own log with its traceback.

    @relation(REQ-AUT-001, scope=function)

    Args:
        request: The request that failed; not read.
        error: The error the load or replay raised.

    Returns:
        An answer with status 500 whose detail is the error's type and message.
    """
    reason = f"{type(error).__name__}: {error}"

    return JSONResponse(status_code=500, content={"detail": reason})


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
