"""Calls of the project's services, shared by the pipelines."""

import logging
import tomllib
from datetime import timedelta
from pathlib import Path

import requests

# The project's config/securities.toml, mounted read-only by compose.yaml.
SECURITIES_FILE = Path("/opt/airflow/project-config/securities.toml")

logger = logging.getLogger(__name__)


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


def post_for_each_security(
    url: str, timeout: timedelta, fields: dict | None = None
) -> dict:
    """Post to a project service once for each configured security, one after the other.

    Each body holds the security's symbol and the given fields. A failed call is logged
    at once, and the calls for the other securities still go out.

    @relation(REQ-AUT-001, scope=function)
    @relation(REQ-AUT-008, scope=function)

    Args:
        url: Address of the service endpoint.
        timeout: How long to wait for each answer.
        fields: Fields every body holds besides the symbol.

    Returns:
        A dictionary: "answers" holds the answer of each security whose call succeeded,
        and "failures" holds one text per failed security, with its symbol and reason.
    """
    with SECURITIES_FILE.open("rb") as file:
        symbols = [entry["symbol"] for entry in tomllib.load(file)["securities"]]
    answers = []
    failures = []
    for symbol in symbols:
        body = {"symbol": symbol} | (fields or {})
        try:
            answer = post_to_service(url, timeout, body)
        except (RuntimeError, requests.RequestException) as error:
            # Each failure is logged at once: if the time limit stops the task, the task
            # log still shows each failure so far.
            failure = f"{symbol}: {error}"
            logger.error(failure)
            failures.append(failure)
            continue
        answers.append(answer)

    return {"answers": answers, "failures": failures}


def fail_on_failures(failures: list[str]) -> None:
    """Fail the task if any security failed, naming each with its reason.

    @relation(REQ-AUT-008, scope=function)

    Args:
        failures: Each security that failed, with its reason.

    Raises:
        RuntimeError: If any security failed; the message names each with its reason.
    """
    if failures:
        raise RuntimeError("Failed for " + "; ".join(failures))
