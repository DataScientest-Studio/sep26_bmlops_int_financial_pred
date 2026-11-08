"""Acceptance tests of the web app requirements (page run against a fake API)."""

import json
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pandas as pd
import pytest
import streamlit as st
from pandas.testing import assert_frame_equal
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.acceptance

PAGE = Path(__file__).resolve().parents[2] / "webapp" / "app.py"
START_CLOSE = 100.0
HISTORY = [
    {"day": "2025-03-12", "close": 98.0},
    {"day": "2025-03-13", "close": START_CLOSE},
]
# Nine different values, so no two scores can be swapped.
SCORES = {
    "model": {"mae": 0.011, "skill": 0.21, "directional_accuracy": 0.56},
    "persistence": {"mae": 0.014, "skill": 0.0, "directional_accuracy": 0.5},
    "mean_change": {"mae": 0.013, "skill": 0.07, "directional_accuracy": 0.52},
}


class FakeApi:
    """A local server that answers fixed JSON and records the GET targets asked for.

    Routes are keyed by method, path and, for POST, the symbol of the body.
    """

    def __init__(self) -> None:
        """Start serving on a free port of 127.0.0.1."""
        self.routes: dict[tuple[str, str, str | None], tuple[int, object]] = {}
        self.requested: list[str] = []
        fake_api = self

        class Handler(BaseHTTPRequestHandler):
            def _answer(self, symbol: str | None) -> None:
                path = self.path.split("?")[0]
                status, body = fake_api.routes.get(
                    (self.command, path, symbol), (404, {"detail": "unknown"})
                )
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self) -> None:
                fake_api.requested.append(self.path)
                self._answer(None)

            def do_POST(self) -> None:
                length = int(self.headers["Content-Length"])
                self._answer(json.loads(self.rfile.read(length))["symbol"])

            def log_message(self, format: str, *args: object) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        Thread(target=self.server.serve_forever, daemon=True).start()

    def serve_security(
        self,
        symbol: str,
        model_version: str,
        change: float,
        mean_change_forecast: float | None,
    ) -> None:
        """Answer history, model results and prediction of a security with a model."""
        self.routes[("GET", f"/securities/{symbol}/history", None)] = (200, HISTORY)
        self.routes[("GET", f"/securities/{symbol}/model", None)] = (
            200,
            {
                "symbol": symbol,
                "model_version": model_version,
                "evaluation_days": 30,
                **SCORES,
                "mean_change_forecast": mean_change_forecast,
            },
        )
        self.routes[("POST", "/predict", symbol)] = (
            200,
            {
                "symbol": symbol,
                "day": "2025-03-14",
                "change": change,
                "model_version": model_version,
                "start_close": START_CLOSE,
                "start_fetched_at": "2025-03-13T22:00:00Z",
            },
        )

    def serve_securities(self, symbols: list[str]) -> None:
        """Answer the list of securities."""
        self.routes[("GET", "/securities", None)] = (200, symbols)


@pytest.fixture
def fake_api() -> Iterator[FakeApi]:
    """A running fake API."""
    api = FakeApi()
    yield api
    api.server.shutdown()
    api.server.server_close()


@pytest.fixture
def open_page(
    fake_api: FakeApi, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[[], AppTest]]:
    """A function that runs the page once against the fake API."""
    monkeypatch.setenv("API_URL", fake_api.url)
    st.cache_data.clear()
    yield lambda: AppTest.from_file(str(PAGE), default_timeout=10).run()
    st.cache_data.clear()


def _forecast_table(rows: list[tuple[str, float | None, float | None]]) -> pd.DataFrame:
    """The forecast table the page shows, one row per forecaster."""
    return pd.DataFrame(rows, columns=["Forecaster", "Change", "Close"])


def test_user_chooses_a_security_and_sees_its_forecasts(
    fake_api: FakeApi, open_page: Callable[[], AppTest]
) -> None:
    """REQ-APP-001: a user chooses a security and sees its latest 60 trading days."""
    securities = ["A", "B"]
    fake_api.serve_securities(securities)
    fake_api.serve_security("A", "1", 0.01, None)
    fake_api.serve_security("B", "2", 0.015, 0.0025)
    page = open_page()

    assert not page.exception
    assert sorted(page.selectbox[0].options) == sorted(securities)
    assert_frame_equal(
        page.dataframe[0].value,
        _forecast_table(
            [
                ("Model version 1", 0.01, 101.0),
                ("Persistence", 0.0, START_CLOSE),
                ("Mean change", None, None),
            ]
        ),
    )

    page.selectbox[0].select("B").run()

    assert not page.exception
    assert "/securities/B/history?days=60" in fake_api.requested
    assert_frame_equal(
        page.dataframe[0].value,
        _forecast_table(
            [
                ("Model version 2", 0.015, 101.5),
                ("Persistence", 0.0, START_CLOSE),
                ("Mean change", 0.0025, 100.25),
            ]
        ),
    )


def test_refused_security_shows_the_reason_instead_of_the_forecasts(
    fake_api: FakeApi, open_page: Callable[[], AppTest]
) -> None:
    """REQ-APP-001: a security without a production model shows the API's reason."""
    reason = "No production model for A"
    fake_api.serve_securities(["A"])
    fake_api.routes[("GET", "/securities/A/history", None)] = (200, HISTORY)
    fake_api.routes[("GET", "/securities/A/model", None)] = (404, {"detail": reason})
    fake_api.routes[("POST", "/predict", "A")] = (404, {"detail": reason})
    page = open_page()

    assert not page.exception
    assert page.info[0].value == reason
    assert len(page.dataframe) == 0


def test_failed_forecast_shows_the_reason_instead_of_the_forecasts(
    fake_api: FakeApi, open_page: Callable[[], AppTest]
) -> None:
    """REQ-APP-001: when the API fails on a request, the page shows its reason."""
    reason = "MLflow is unreachable"
    fake_api.serve_securities(["A"])
    fake_api.serve_security("A", "1", 0.01, 0.0025)
    fake_api.routes[("POST", "/predict", "A")] = (500, {"detail": reason})
    page = open_page()

    assert not page.exception
    assert reason in page.error[0].value
    assert len(page.dataframe) == 0


def test_model_results_put_the_model_next_to_both_baselines(
    fake_api: FakeApi, open_page: Callable[[], AppTest]
) -> None:
    """REQ-APP-003: the page shows the scores of the model next to both baselines."""
    fake_api.serve_securities(["A"])
    fake_api.serve_security("A", "1", 0.01, 0.0025)
    page = open_page()

    assert not page.exception
    assert_frame_equal(
        page.dataframe[1].value,
        pd.DataFrame(
            [
                ("Model", 0.011, 0.21, 0.56),
                ("Persistence", 0.014, 0.0, 0.5),
                ("Mean change", 0.013, 0.07, 0.52),
            ],
            columns=["Forecaster", "mae", "skill", "directional_accuracy"],
        ),
    )
