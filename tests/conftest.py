"""Fixtures shared by all tests.

Tests use the settings of `.env.example`, which `make test` loads, and of the files in
config/. Database tests need the local PostgreSQL server (`make db`) with the login
from `.env.example`. Each pytest-xdist worker gets its own database, created from
`db/init/`, so workers never share data.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable, Iterator, Sequence
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mlflow import MlflowClient
from sqlalchemy import Engine, make_url, text

from forecasting.api.app import create_app
from forecasting.api.dependencies import get_engine, get_settings
from forecasting.config import Settings, load_settings
from forecasting.db import connect, create_database, drop_database
from forecasting.drift_checks import (
    DRIFT_CHECKS_EXPERIMENT_NAME,
    REPLAY_DRIFT_CHECKS_EXPERIMENT_NAME,
)
from forecasting.train import EXPERIMENT_NAME, REPLAY_EXPERIMENT_NAME
from tests.fakes import FETCHED_AT, INDICES, SECURITIES

# Seconds a throwaway MLflow server may take to answer its health check.
MLFLOW_START_LIMIT = 60


@pytest.fixture(scope="session")
def example_settings() -> Settings:
    """Settings from `.env.example`, which `make test` loads, and from config/."""
    return load_settings()


@pytest.fixture(scope="session")
def database_url(example_settings: Settings, worker_id: str) -> Iterator[str]:
    """Create an empty project database for this worker; drop it afterwards."""
    url = make_url(example_settings.database_url)
    name = f"{url.database}_test_{worker_id}"
    test_url = url.set(database=name).render_as_string(hide_password=False)
    try:
        create_database(test_url)
    except psycopg.OperationalError:
        pytest.fail(
            "Cannot log in to the database with the values of .env.example; "
            "start it with make db and keep those values in .env",
            pytrace=False,
        )
    yield test_url
    drop_database(test_url)


@pytest.fixture
def replay_url(example_settings: Settings, worker_id: str) -> Iterator[str]:
    """URL of this worker's replay database, which does not exist yet; dropped after."""
    url = make_url(example_settings.replay_database_url)
    name = f"{url.database}_test_{worker_id}"
    test_url = url.set(database=name).render_as_string(hide_password=False)
    drop_database(test_url)
    yield test_url
    drop_database(test_url)


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    """Engine of this worker's database, emptied before each test."""
    engine = connect(database_url)
    with engine.begin() as connection:
        connection.execute(
            text("TRUNCATE prices, splits, dividends, loads, predictions")
        )
    yield engine
    engine.dispose()


@pytest.fixture
def store_forecast(engine: Engine) -> Callable[..., None]:
    """Give a test a function that stores one forecast row in this worker's database."""

    def store(
        symbol: str,
        day: str,
        requested_at: str,
        scheduled: bool,
        changes: Sequence[float],
    ) -> None:
        """Insert a forecast of `day` requested at `requested_at`, both ISO format."""
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO predictions (symbol, day, change, model_version, "
                    "start_close, start_fetched_at, change_1, change_2, change_3, "
                    "change_4, change_5, requested_at, scheduled) VALUES "
                    "(:symbol, :day, 0.99, 'v1', 100, :fetched_at, :change_1, "
                    ":change_2, :change_3, :change_4, :change_5, :requested_at, "
                    ":scheduled)"
                ),
                {
                    "symbol": symbol,
                    "day": date.fromisoformat(day),
                    "fetched_at": FETCHED_AT,
                    "change_1": changes[0],
                    "change_2": changes[1],
                    "change_3": changes[2],
                    "change_4": changes[3],
                    "change_5": changes[4],
                    "requested_at": datetime.fromisoformat(requested_at),
                    "scheduled": scheduled,
                },
            )

    return store


@pytest.fixture
def settings(
    example_settings: Settings, database_url: str, replay_url: str, tmp_path: Path
) -> Settings:
    """Test settings on this worker's databases, test symbols, own folders and MLflow.

    MLflow keeps its records in a file under the test's folder; the experiments are
    created upfront so their model files and drift reports land there too.
    """
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    mlflow_tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    artifacts = (tmp_path / "artifacts").as_uri()
    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    client.create_experiment(EXPERIMENT_NAME, artifact_location=artifacts)
    client.create_experiment(REPLAY_EXPERIMENT_NAME, artifact_location=artifacts)
    client.create_experiment(DRIFT_CHECKS_EXPERIMENT_NAME, artifact_location=artifacts)
    client.create_experiment(
        REPLAY_DRIFT_CHECKS_EXPERIMENT_NAME, artifact_location=artifacts
    )

    return replace(
        example_settings,
        database_url=database_url,
        replay_database_url=replay_url,
        dataset_dir=dataset_dir,
        dataset_remote=str(tmp_path / "dataset_remote"),
        mlflow_tracking_uri=mlflow_tracking_uri,
        securities=SECURITIES,
        indices=INDICES,
    )


def _wait_until_healthy(
    server: subprocess.Popen[bytes], url: str, log_path: Path
) -> None:
    """Return once the MLflow server at `url` answers its health check.

    Fails the test run if the server exits or does not answer within
    `MLFLOW_START_LIMIT` seconds; the failure names the server's log and, if the
    server exited, its exit status.
    """
    deadline = time.monotonic() + MLFLOW_START_LIMIT
    while time.monotonic() < deadline:
        if server.poll() is not None:
            pytest.fail(
                f"MLflow server exited with status {server.returncode}; "
                f"log: {log_path}",
                pytrace=False,
            )
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2):
                return
        except OSError:
            time.sleep(0.2)
    pytest.fail(
        f"MLflow server did not answer within {MLFLOW_START_LIMIT} s (still running); "
        f"log: {log_path}",
        pytrace=False,
    )


@pytest.fixture(scope="session")
def mlflow_server_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Start a throwaway MLflow server on 127.0.0.1 for this worker; stop it at the end.

    The server keeps its records and its log in a folder of its own; it starts only in a
    worker whose tests ask for it.
    """
    folder = tmp_path_factory.mktemp("mlflow_server")
    log_path = folder / "server.log"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with log_path.open("wb") as log:
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "mlflow",
                "server",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--workers",
                "1",
                "--backend-store-uri",
                f"sqlite:///{folder / 'mlflow.db'}",
                "--default-artifact-root",
                str(folder / "artifacts"),
            ],
            cwd=folder,
            # The tests run no MLflow jobs, so the server starts without its job runner.
            env=os.environ | {"MLFLOW_SERVER_ENABLE_JOB_EXECUTION": "false"},
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    url = f"http://127.0.0.1:{port}"
    try:
        _wait_until_healthy(server, url, log_path)
        yield url
    finally:
        server.terminate()
        try:
            server.wait(timeout=30)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


@pytest.fixture
def app(engine: Engine, settings: Settings) -> FastAPI:
    """API whose endpoints use the test database and settings."""
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_settings] = lambda: settings

    return app


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    """Client of the `app` fixture's API."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def change_settings(app: FastAPI, settings: Settings) -> Callable[..., None]:
    """Give a test a function that changes settings the `app` fixture's API uses."""

    def change(**changes: Any) -> None:
        """Make the API use the test settings with `changes`."""
        changed = replace(settings, **changes)
        app.dependency_overrides[get_settings] = lambda: changed

    return change
