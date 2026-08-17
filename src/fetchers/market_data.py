from __future__ import annotations

from datetime import UTC, datetime
import os

import requests

from src.fetchers.provider_audit import record_alpha_symbol, record_provider
from src.markets.performance import calculate_return_table


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"


def fetch_yahoo_history(symbol: str, range_: str = "1mo", interval: str = "1d") -> list[dict]:
    response = requests.get(
        YAHOO_CHART_URL.format(symbol=symbol),
        params={"range": range_, "interval": interval},
        timeout=10,
        headers={"User-Agent": "WolfResearch/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    result = payload["chart"]["result"][0]
    timestamps = result.get("timestamp") or []
    closes = result["indicators"]["quote"][0].get("close") or []
    rows = []
    for ts, close in zip(timestamps, closes, strict=False):
        if close is None:
            continue
        rows.append({"date": datetime.fromtimestamp(ts, UTC).date().isoformat(), "close": float(close)})
    return rows


def pct_change(current: float, previous: float | None) -> float:
    if previous in (None, 0):
        return 0.0
    return round(((current / previous) - 1) * 100, 2)


def fetch_alpha_vantage_history(function_name: str, symbol: str, **params: str) -> list[dict]:
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        raise ValueError("ALPHA_VANTAGE_API_KEY is not configured")
    payload = {"function": function_name, "apikey": api_key, **params}
    if symbol:
        payload["symbol"] = symbol
    response = requests.get(ALPHA_VANTAGE_URL, params=payload, timeout=20)
    response.raise_for_status()
    data = response.json()
    if "Error Message" in data:
        raise ValueError(data["Error Message"])
    if "Note" in data:
        raise ValueError("Alpha Vantage rate limit or notice returned")
    time_series = (
        data.get("Time Series FX (Daily)")
        or data.get("Time Series (Daily)")
        or data.get("Daily Time Series")
    )
    if not time_series:
        raise ValueError("No Alpha Vantage daily time series returned")
    rows = []
    for observed_at, values in sorted(time_series.items()):
        close = values.get("4. close") or values.get("5. adjusted close")
        if close is None:
            continue
        rows.append({"date": observed_at, "close": float(close)})
    record_alpha_symbol(symbol or f"{params.get('from_symbol')}/{params.get('to_symbol')}")
    return rows


def alpha_market_row(label: str, symbol: str, driver: str, source_url: str, *, function: str = "TIME_SERIES_DAILY") -> dict:
    if function == "FX_DAILY":
        from_symbol, to_symbol = symbol.split("/")
        history = fetch_alpha_vantage_history("FX_DAILY", "", from_symbol=from_symbol, to_symbol=to_symbol, outputsize="compact")
    else:
        history = fetch_alpha_vantage_history(function, symbol, outputsize="compact")
    if not history:
        raise ValueError(f"No Alpha Vantage history returned for {label}")
    perf = calculate_return_table(history)
    return {
        "label": label,
        "last": perf["latest"],
        "one_week_change": perf["one_week"],
        "one_month_change": perf["one_month"],
        "ytd_change": perf["ytd"],
        "latest_date": perf["latest_date"],
        "is_stale": perf["is_stale"],
        "driver": driver,
        "source": {"name": "Alpha Vantage", "url": source_url},
    }


def market_row(label: str, symbol: str, driver: str, source_url: str) -> dict:
    history = fetch_yahoo_history(symbol, range_="1y")
    if not history:
        raise ValueError(f"No price history returned for {symbol}")
    perf = calculate_return_table(history)
    record_provider("yahoo_finance")
    return {
        "label": label,
        "last": perf["latest"],
        "one_week_change": perf["one_week"],
        "one_month_change": perf["one_month"],
        "ytd_change": perf["ytd"],
        "latest_date": perf["latest_date"],
        "is_stale": perf["is_stale"],
        "driver": driver,
        "source": {"name": "Yahoo Finance", "url": source_url},
    }
