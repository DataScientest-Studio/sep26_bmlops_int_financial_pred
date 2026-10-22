"""Fixtures shared by all tests.

Tests use the settings of `.env.example`, which `make test` loads. Database tests
need the local PostgreSQL server (`make db`) with the login from `.env.example`. Each
pytest-xdist worker gets its own database, created from `db/init/`, so workers never
share data.
"""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, make_url, text

from forecasting.api.app import create_app
from forecasting.api.dependencies import get_engine, get_settings
from forecasting.config import Settings, load_settings
from forecasting.db import connect, create_database, drop_database
from tests.fakes import INDICES, SECURITIES


@pytest.fixture(scope="session")
def example_settings() -> Settings:
    """Settings from `.env.example`, which `make test` loads."""
    return load_settings()


@pytest.fixture(scope="session")
def database_url(example_settings: Settings, worker_id: str) -> Iterator[str]:
    """Create an empty project database for this worker; drop it afterwards."""
    url = make_url(example_settings.database_url)
    name = f"{url.database}_test_{worker_id}"
    test_url = url.set(database=name).render_as_string(hide_password=False)
    create_database(test_url)
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
        connection.execute(text("TRUNCATE prices, splits, dividends"))
    yield engine
    engine.dispose()


@pytest.fixture
def settings(example_settings: Settings, database_url: str, tmp_path: Path) -> Settings:
    """Test settings on this worker's database, test symbols and own folders."""
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()

    return replace(
        example_settings,
        database_url=database_url,
        model_dir=tmp_path / example_settings.model_dir,
        dataset_dir=dataset_dir,
        dataset_remote=str(tmp_path / "dataset_remote"),
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
