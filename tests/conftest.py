"""Fixtures shared by all tests.

Tests use the settings of `.env.example`, which `make test` loads. Database tests
need the local PostgreSQL server (`make db`) with the login from `.env.example`. Each
pytest-xdist worker gets its own database, created from `db/init/`, so workers never
share data.
"""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import Engine, make_url, text

from forecasting.api.app import create_app
from forecasting.api.dependencies import get_engine, get_settings
from forecasting.config import Settings, load_settings
from forecasting.db import connect
from tests.fakes import INDICES, SECURITIES

INIT_DIR = Path(__file__).parent.parent / "db" / "init"


@pytest.fixture(scope="session")
def example_settings() -> Settings:
    """Settings from `.env.example`, which `make test` loads."""
    return load_settings()


@pytest.fixture(scope="session")
def database_url(example_settings: Settings, worker_id: str) -> Iterator[str]:
    """Create an empty project database for this worker; drop it afterwards."""
    # SQLAlchemy names its driver in the URL (postgresql+psycopg://); psycopg itself
    # takes only the plain postgresql:// form.
    sqlalchemy_url = make_url(example_settings.database_url)
    name = f"{sqlalchemy_url.database}_test_{worker_id}"
    psycopg_url = sqlalchemy_url.set(drivername="postgresql")
    admin_url = psycopg_url.render_as_string(hide_password=False)
    url = sqlalchemy_url.set(database=name).render_as_string(hide_password=False)
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name))
        )
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    engine = connect(url).execution_options(isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        for script in sorted(INIT_DIR.glob("*.sql")):
            connection.exec_driver_sql(script.read_text())
    engine.dispose()
    yield url
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)
            )
        )


@pytest.fixture
def engine(database_url: str) -> Iterator[Engine]:
    """Engine of this worker's database, emptied before each test."""
    engine = connect(database_url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE prices"))
    yield engine
    engine.dispose()


@pytest.fixture
def settings(example_settings: Settings, database_url: str, tmp_path: Path) -> Settings:
    """Test settings on this worker's database, test symbols and model folder."""
    return replace(
        example_settings,
        database_url=database_url,
        model_dir=tmp_path / example_settings.model_dir,
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
