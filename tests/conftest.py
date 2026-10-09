"""Fixtures shared by all tests.

Database tests need the local PostgreSQL server (`make db`) and the variables of
`.env`. Each pytest-xdist worker gets its own database, created from
`db/init/`, so workers never share data.
"""

import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import text

from forecasting.api.app import create_app
from forecasting.api.dependencies import get_engine, get_settings
from forecasting.config import Settings
from forecasting.db import connect
from tests.fakes import SECURITIES

INIT_DIR = Path(__file__).parent.parent / "db" / "init"


@pytest.fixture(scope="session")
def database_url(worker_id: str):
    """Create an empty project database for this worker; drop it afterwards."""
    env = os.environ
    name = f"forecasting_test_{worker_id}"
    server = dict(
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        host=env["POSTGRES_HOST"],
        port=env["POSTGRES_PORT"],
    )
    with psycopg.connect(dbname=env["POSTGRES_DB"], autocommit=True, **server) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name))
        )
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    with psycopg.connect(dbname=name, autocommit=True, **server) as db:
        for script in sorted(INIT_DIR.glob("*.sql")):
            db.execute(script.read_text())
    yield (
        f"postgresql+psycopg://{server['user']}:{server['password']}"
        f"@{server['host']}:{server['port']}/{name}"
    )
    with psycopg.connect(dbname=env["POSTGRES_DB"], autocommit=True, **server) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)
            )
        )


@pytest.fixture
def engine(database_url: str):
    """Engine of this worker's database, emptied before each test."""
    engine = connect(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE prices"))
    yield engine
    engine.dispose()


@pytest.fixture
def settings(database_url: str, tmp_path: Path) -> Settings:
    """Settings for the test securities, with models saved under `tmp_path`."""
    return Settings(database_url, tmp_path / "models", SECURITIES)


@pytest.fixture
def client(engine, settings: Settings):
    """API client whose endpoints use the test database and settings."""
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as client:
        yield client
