"""The answer the API and the data service give when a request fails unexpectedly."""

from fastapi import Request
from fastapi.responses import JSONResponse


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
    reason = f"{type(error).__name__}: {error}"

    return JSONResponse(status_code=500, content={"detail": reason})
