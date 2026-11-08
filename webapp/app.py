"""Web app: a security's recent closes, next-trading-day forecasts and model results.

@relation(REQ-APP-001, REQ-APP-002, REQ-APP-003, scope=file)
"""

import os
from typing import Any

import httpx2
import pandas as pd
import streamlit as st

# Address of the API; Compose sets it to the api service.
API_URL = os.environ["API_URL"]
# Trading days of closes the chart shows, about three months.
HISTORY_DAYS = 60
# Seconds to wait for an answer; a forecast first loads the model from MLflow.
TIMEOUT_SECONDS = 30
NOTICE = "These forecasts are not investment advice."


class _Refused(Exception):
    """The API refused a request and gave its reason."""


class _Failed(Exception):
    """The API failed on a request and gave its reason."""


def _answer(response: httpx2.Response) -> Any:
    """Return the body of a successful answer.

    Args:
        response: Answer of the API.

    Returns:
        The body of the answer, decoded from JSON.

    Raises:
        _Refused: if the API refuses the request (404), with its reason.
        _Failed: if the API fails on the request (500), with its reason.
        httpx2.HTTPStatusError: if the API answers with another error.
    """
    if response.status_code == 404:
        raise _Refused(response.json()["detail"])
    if response.status_code == 500:
        raise _Failed(response.json()["detail"])
    response.raise_for_status()

    return response.json()


def _get(path: str, **params: int) -> Any:
    """Return the body of the API's answer to a GET request on the path."""
    response = httpx2.get(f"{API_URL}{path}", params=params, timeout=TIMEOUT_SECONDS)

    return _answer(response)


@st.cache_data
def _securities() -> list[str]:
    """Return the securities the API lists."""
    return _get("/securities")


# Streamlit runs this script again on every click. The API stores every forecast it
# makes, so a forecast is asked once per security, latest close and production model:
# a new day, a final close replacing a provisional one or a newly promoted model asks
# again, a click does not. The model is told apart by all its results, because the
# member's and the replay's models each number their versions from 1. A refusal or
# failure is not cached.
@st.cache_data
def _forecast(
    symbol: str, latest: dict[str, Any], results: dict[str, Any]
) -> dict[str, Any]:
    """Return the production model's forecast for the security's next trading day."""
    url = f"{API_URL}/predict"
    response = httpx2.post(url, json={"symbol": symbol}, timeout=TIMEOUT_SECONDS)

    return _answer(response)


st.set_page_config(page_title="Financial forecasting")
st.warning(NOTICE)
st.title("Next-trading-day forecast")
try:
    symbol = st.selectbox("Security", _securities())
    rows = _get(f"/securities/{symbol}/history", days=HISTORY_DAYS)
    # Without stored prices there is no chart; the model results' refusal says why.
    if rows:
        closes = pd.DataFrame(rows)
        closes["day"] = pd.to_datetime(closes["day"])
        st.line_chart(closes, x="day", y="close")
    results = _get(f"/securities/{symbol}/model")
    predicted = _forecast(symbol, rows[-1], results)
except _Refused as refusal:
    st.info(str(refusal))
    st.stop()
except _Failed as failure:
    st.error(f"The API could not answer: {failure}")
    st.stop()

# Persistence forecasts no change; the mean-change baseline forecasts the mean change
# of the model's training days, which a training run may not have recorded.
start = predicted["start_close"]
mean_change = results["mean_change_forecast"]
st.subheader(f"Forecast for {predicted['day']}")
st.caption(f"From the close {start:.2f}, fetched {predicted['start_fetched_at']}")
forecasts = pd.DataFrame(
    {
        "Forecaster": [
            f"Model version {predicted['model_version']}",
            "Persistence",
            "Mean change",
        ],
        "Change": [predicted["change"], 0.0, mean_change],
    }
)
forecasts["Close"] = start * (1 + forecasts["Change"])
st.dataframe(forecasts, hide_index=True)
if mean_change is None:
    st.caption("The mean-change forecast was not recorded for this model.")

st.subheader("Model results")
st.caption(f"On the {results['evaluation_days']} evaluation days of its training run")
scores = pd.DataFrame(
    [
        {"Forecaster": "Model", **results["model"]},
        {"Forecaster": "Persistence", **results["persistence"]},
        {"Forecaster": "Mean change", **results["mean_change"]},
    ]
)
st.dataframe(scores, hide_index=True)
