"""Data service: runs the load and the replay for the scheduled pipelines."""

from datetime import date

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from forecasting.commands import run_load, run_replay
from forecasting.load import LoadReport

app = FastAPI(title="Financial forecasting data service")


@app.exception_handler(Exception)
def report_failure(request: Request, error: Exception) -> JSONResponse:
    """Answer a failed load or replay with its reason, so the pipeline can show it.

    The error still reaches the service's own log with its traceback.

    @relation(REQ-AUT-001, scope=function)
    """
    reason = f"{type(error).__name__}: {error}"

    return JSONResponse(status_code=500, content={"detail": reason})


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the service is running.

    @relation(REQ-AUT-003, scope=function)
    """
    return {"status": "ok"}


@app.post("/load")
def load() -> LoadReport:
    """Run the load and answer with its report.

    @relation(REQ-DAT-001, scope=function)
    @relation(REQ-DAT-002, scope=function)
    """
    return run_load()


@app.post("/replay")
def replay() -> dict[str, date | None]:
    """Copy the next stored day into the replay database and answer with it.

    Answers with no day when nothing is left to replay.

    @relation(REQ-DAT-003, scope=function)
    """
    return {"day": run_replay()}
