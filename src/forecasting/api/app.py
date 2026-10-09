"""Creation of the FastAPI application."""

from fastapi import FastAPI

from forecasting.api.routes import router


def create_app() -> FastAPI:
    """Create the API with all endpoints.

    Nothing is loaded at creation; settings, database and model are opened on
    first use, so tests can replace them.

    @relation(REQ-SVC-001, scope=function)
    @relation(REQ-SVC-002, scope=function)

    Returns:
        The application, ready for uvicorn.
    """
    app = FastAPI(
        title="Financial forecasting service",
        description="Next-trading-day price change forecasts. Not investment advice.",
    )
    app.include_router(router)
    return app


app = create_app()
