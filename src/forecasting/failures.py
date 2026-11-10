"""The reason the API, the data service and the commands show when something fails.

The API and the data service answer with it when a request fails unexpectedly.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


def failure_reason(error: Exception) -> str:
    """Return the error's type name, a colon, a space and its message as it was raised.

    @relation(REQ-AUT-009, scope=function)

    Args:
        error: The error that was raised.

    Returns:
        The text, for example "ValueError: no such symbol".
    """
    return f"{type(error).__name__}: {error}"


def report_failure(request: Request, error: Exception) -> JSONResponse:
    """Answer a failed request with its reason, so a pipeline can show it.

    The error still reaches the service's own log with its traceback.

    @relation(REQ-AUT-001, scope=function)

    Args:
        request: The request that failed; not read.
        error: The error the request raised.

    Returns:
        An answer with status 500 whose detail is the error's type and message.
    """
    return JSONResponse(status_code=500, content={"detail": failure_reason(error)})
