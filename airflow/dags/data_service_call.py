"""Calls of the data service, shared by the pipelines."""

from datetime import timedelta

import requests


def post_to_data_service(url: str, timeout: timedelta) -> dict:
    """Post to the data service and return its answer.

    @relation(REQ-AUT-001, scope=function)

    Raises:
        RuntimeError: If the service answers with an error; the message carries the
            reason it answered with, so the task's log shows it.
    """
    response = requests.post(url, timeout=timeout.total_seconds())
    if not response.ok:
        answer = f"{response.status_code}: {response.text}"
        raise RuntimeError(f"The data service answered {answer}")

    return response.json()
