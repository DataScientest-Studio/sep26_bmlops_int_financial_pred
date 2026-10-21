"""Data service: runs the load and the replay for the scheduled pipelines."""

from datetime import date

from fastapi import FastAPI

from forecasting.commands import run_load, run_replay
from forecasting.load import LoadReport

app = FastAPI(title="Financial forecasting data service")


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
