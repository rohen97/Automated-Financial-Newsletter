from __future__ import annotations

from src.fetchers.base import sample_series
from src.fetchers.market_data import alpha_market_row
from src.fetchers.provider_audit import record_error, record_fallback


DEFAULT_LEVELS = {
    "Brent": 82.0,
    "WTI": 78.0,
    "Gold": 2350.0,
    "Copper": 4.5,
    "Natural Gas / LNG proxy": 2.7,
}
ALPHA_SYMBOLS = {
    "Brent": "BNO",
    "WTI": "USO",
    "Gold": "GLD",
    "Copper": "CPER",
    "Natural Gas / LNG proxy": "UNG",
}
DRIVERS = {
    "Brent": "OPEC supply discipline / demand balance",
    "WTI": "US inventory cycle / refinery demand",
    "Gold": "Real yields / safe-haven demand",
    "Copper": "China growth expectations",
    "Natural Gas / LNG proxy": "Weather demand / LNG flow signals",
}


def fetch_commodities_data(tickers_config: dict) -> list[dict]:
    rows = []
    for item in tickers_config.get("commodities", []):
        label = item["label"]
        alpha_symbol = ALPHA_SYMBOLS.get(label)
        if alpha_symbol:
            try:
                rows.append(
                    alpha_market_row(
                        label,
                        alpha_symbol,
                        DRIVERS.get(label, "Supply-demand balance"),
                        f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={alpha_symbol}",
                    )
                )
                continue
            except Exception as exc:
                record_error("alpha_vantage", f"{label}: {exc}")
                record_fallback()
        row = sample_series(label, DEFAULT_LEVELS.get(label, 100.0))
        row["driver"] = DRIVERS.get(label, "Supply-demand balance")
        rows.append(row)
    return rows
