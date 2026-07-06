from __future__ import annotations

from src.fetchers.base import sample_series


DEFAULT_LEVELS = {"USD/SGD": 1.35, "AUD/USD": 0.66, "EUR/USD": 1.08, "DXY": 104.2}


def fetch_fx_data(tickers_config: dict) -> list[dict]:
    rows = []
    for item in tickers_config.get("fx", []):
        label = item["label"]
        rows.append(sample_series(label, DEFAULT_LEVELS.get(label, 1.0)))
    return rows
