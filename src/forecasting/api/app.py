"""Creation of the FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from forecasting.api.dependencies import get_settings
from forecasting.api.metrics import add_metrics
from forecasting.api.routes import router


@asynccontextmanager
async def read_settings_at_start(app: FastAPI) -> AsyncIterator[None]:
    """Read the settings at start, so a refused setting stops the start.

    @relation(REQ-AUT-003, scope=function)

    Args:
        app: The application being started; not read.
    """
    get_settings()
    yield


def create_app() -> FastAPI:
    """Create the API with all endpoints.

    Settings are read when the application starts, and a setting that is refused
    stops the start; database and model are opened on first use, so tests can
    replace them.

    @relation(REQ-SVC-001, scope=function)
    @relation(REQ-SVC-002, scope=function)

    Returns:
        The application, ready for uvicorn.
    """
    app = FastAPI(
        title="Financial forecasting service",
        description="Next-trading-day price change forecasts. Not investment advice.",
        lifespan=read_settings_at_start,
    )
    app.include_router(router)
    add_metrics(app)

    return app


app = create_app()
