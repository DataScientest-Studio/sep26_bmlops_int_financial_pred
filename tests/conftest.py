"""Fixtures shared by all tests.

Tests use the settings of `.env.example`, which `make test` loads, and of the files in
config/. Database tests need the local PostgreSQL server (`make db`) with the login
from `.env.example`. Each pytest-xdist worker gets its own database, created from
`db/init/`, so workers never share data.
"""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from mlflow import MlflowClient
from sqlalchemy import Engine, make_url, text

from forecasting.api.app import create_app
from forecasting.api.dependencies import get_engine, get_settings
from forecasting.config import Settings, load_settings
from forecasting.db import connect, create_database, drop_database
from forecasting.train import EXPERIMENT_NAME, REPLAY_EXPERIMENT_NAME
from tests.fakes import INDICES, SECURITIES


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
        connection.execute(text("TRUNCATE prices, splits, dividends, loads"))
    yield engine
    engine.dispose()


@pytest.fixture
def settings(
    example_settings: Settings, database_url: str, replay_url: str, tmp_path: Path
) -> Settings:
    """Test settings on this worker's databases, test symbols, own folders and MLflow.

    MLflow keeps its records in a file under the test's folder; the experiments are
    created upfront so their model files land there too.
    """
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    mlflow_tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    artifacts = (tmp_path / "artifacts").as_uri()
    client = MlflowClient(tracking_uri=mlflow_tracking_uri)
    client.create_experiment(EXPERIMENT_NAME, artifact_location=artifacts)
    client.create_experiment(REPLAY_EXPERIMENT_NAME, artifact_location=artifacts)

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


@pytest.fixture
def client(engine: Engine, settings: Settings) -> Iterator[TestClient]:
    """API client whose endpoints use the test database and settings."""
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client
