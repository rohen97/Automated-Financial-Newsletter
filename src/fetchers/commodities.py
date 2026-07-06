from __future__ import annotations

from src.fetchers.base import sample_series


DEFAULT_LEVELS = {
    "Brent": 82.0,
    "WTI": 78.0,
    "Gold": 2350.0,
    "Copper": 4.5,
    "Natural Gas / LNG proxy": 2.7,
}


def fetch_commodities_data(tickers_config: dict) -> list[dict]:
    return [sample_series(item["label"], DEFAULT_LEVELS.get(item["label"], 100.0)) for item in tickers_config.get("commodities", [])]
