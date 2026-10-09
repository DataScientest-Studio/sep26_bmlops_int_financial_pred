"""Shared parts the endpoints receive; tests replace them."""

from functools import cache

from sqlalchemy import Engine

from forecasting.config import Settings, load_settings
from forecasting.db import connect


@cache
def get_settings() -> Settings:
    """Return the settings, read once per process.

    @relation(REQ-SVC-001, scope=function)
    """
    return load_settings()


@cache
def get_engine() -> Engine:
    """Return the engine of the project database, created once per process.

    @relation(REQ-SVC-001, scope=function)
    """
    return connect(get_settings().database_url)
