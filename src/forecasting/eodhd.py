"""Daily prices, splits and dividends from EODHD (eodhd.com)."""

import logging
from datetime import UTC, date, datetime
from typing import Any

import httpx2
import pandas as pd

from forecasting.db import DIVIDEND_COLUMNS, PRICE_COLUMNS, SPLIT_COLUMNS

API_URL = "https://eodhd.com/api"
# Seconds to wait for each network step (connecting, each read of the answer):
TIMEOUT = 60

# EODHD takes the key in the URL, and httpx2 logs every URL at INFO level:
logging.getLogger("httpx2").setLevel(logging.WARNING)


class EodhdSource:
    """The EODHD data source, read with one member's own key.

    Delivers what `forecasting.load.PriceSource` describes.

    @relation(REQ-DAT-001, scope=class)
    """

    def __init__(self, api_key: str) -> None:
        """Keep the key that every request sends.

        Args:
            api_key: The member's own EODHD key.

        Raises:
            ValueError: If the key is empty.
        """
        if not api_key:
            raise ValueError("The EODHD key is empty; set EODHD_API_KEY in .env")
        self._api_key = api_key

    def fetch_history(self, symbol: str, start: date) -> pd.DataFrame:
        """Fetch the daily price history of one security from a first day on.

        One request, one call, however many days it covers. The fetch time is taken
        before the request is sent, so a quote fetched around the close counts as
        provisional rather than final.

        Args:
            symbol: Ticker as EODHD names it, for example "AAPL.US".
            start: First day to deliver; a plan with a shorter history starts later.

        Returns:
            One row per day, as `forecasting.load.PriceSource.fetch_history` describes.
        """
        fetched_at = datetime.now(UTC)
        rows = self._get(f"eod/{symbol}", {"from": start.isoformat()})
        columns = ["date", "open", "high", "low", "close", "volume"]
        history = pd.DataFrame(rows, columns=columns)
        days = [date.fromisoformat(text) for text in history["date"]]
        history = history.assign(day=days, fetched_at=fetched_at)

        return history[PRICE_COLUMNS]

    def fetch_splits(self, symbol: str) -> pd.DataFrame:
        """Fetch all splits of one security.

        EODHD writes each ratio as a fraction in text, for example "4.000000/1.000000"
        for a 4-for-1 split; it is read as data, never run as code (see `_ratio`).

        Args:
            symbol: Ticker as EODHD names it, for example "AAPL.US".

        Returns:
            One row per split, as `forecasting.load.PriceSource.fetch_splits` describes.

        Raises:
            ValueError: If a split is not two numbers joined by "/".
            ZeroDivisionError: If a split has zero old shares.
        """
        rows = self._get(f"splits/{symbol}", {})
        days = [date.fromisoformat(row["date"]) for row in rows]
        ratios = [_ratio(row["split"]) for row in rows]

        return pd.DataFrame({"day": days, "ratio": ratios}, columns=SPLIT_COLUMNS)

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """Fetch all dividends of one security.

        The amount is EODHD's unadjusted value: the amount paid per share as
        announced, not corrected for later splits.

        Args:
            symbol: Ticker as EODHD names it, for example "AAPL.US".

        Returns:
            One row per dividend, as `forecasting.load.PriceSource.fetch_dividends`
            describes.
        """
        rows = self._get(f"div/{symbol}", {})
        dividends = {
            "day": [date.fromisoformat(row["date"]) for row in rows],
            "amount": [row["unadjustedValue"] for row in rows],
            "currency": [row["currency"] for row in rows],
        }

        return pd.DataFrame(dividends, columns=DIVIDEND_COLUMNS)

    def _get(self, path: str, options: dict[str, str]) -> Any:
        """Send one request to EODHD and return its answer as parsed JSON.

        Args:
            path: The API path, for example "eod/AAPL.US".
            options: Further query options, for example {"from": "2025-01-02"}.

        Returns:
            The answer's JSON list.

        Raises:
            RuntimeError: If EODHD answers with another status than 200 or with no
                list. The message names the path only, never the URL, which carries
                the key.
        """
        query = {"api_token": self._api_key, "fmt": "json", **options}
        response = httpx2.get(f"{API_URL}/{path}", params=query, timeout=TIMEOUT)
        if response.status_code != 200:
            raise RuntimeError(f"EODHD answered {response.status_code} for {path}")
        answer = response.json()
        if not isinstance(answer, list):
            raise RuntimeError(f"EODHD answered no list for {path}")

        return answer


def _ratio(split: str) -> float:
    """Read EODHD's split text, new shares per old shares, as their quotient.

    The fraction is read as two numbers and divided, never evaluated as a formula:
    evaluating text from a web service would run whatever it contains as code.

    Args:
        split: EODHD's split text.

    Returns:
        New shares per old share: 4.0 for "4.000000/1.000000", 0.05 for
        "1.000000/20.000000".

    Raises:
        ValueError: If the text is not two numbers joined by "/".
        ZeroDivisionError: If the old shares are zero.
    """
    new, _, old = split.partition("/")

    return float(new) / float(old)
