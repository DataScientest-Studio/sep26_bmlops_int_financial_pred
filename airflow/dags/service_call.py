"""Calls of the project's services, shared by the pipelines."""

from datetime import timedelta

import requests


def post_to_service(url: str, timeout: timedelta, body: dict | None = None) -> dict:
    """Post the body to a project service and return its answer.

    @relation(REQ-AUT-001, scope=function)

    Args:
        url: Address of the service endpoint.
        timeout: How long to wait for the answer.
        body: JSON body to post, none for an empty request.

    Returns:
        The service's JSON answer.

    Raises:
        RuntimeError: If the service answers with an error; the message carries the
            address and the reason it answered with, so the task's log shows it.
        requests.RequestException: If the service cannot be reached or does not answer
            in time.
    """
    response = requests.post(url, json=body, timeout=timeout.total_seconds())
    if not response.ok:
        answer = f"{response.status_code}: {response.text}"
        raise RuntimeError(f"{url} answered {answer}")

    return response.json()
