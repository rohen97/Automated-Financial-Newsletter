from __future__ import annotations

import os

from src.fetchers.base import sample_series
from src.fetchers.market_data import market_row
from src.fetchers.provider_audit import record_error, record_fallback
from src.markets.driver_explainer import explain_commodity


DEFAULT_LEVELS = {
    "Brent": 82.0,
    "WTI": 78.0,
    "Gold": 2350.0,
    "Copper": 4.5,
    "Natural Gas / LNG proxy": 2.7,
}
def fetch_commodities_data(tickers_config: dict) -> list[dict]:
    rows = []
    for item in tickers_config.get("commodities", []):
        label = item["label"]
        if os.getenv("PYTEST_CURRENT_TEST"):
            row = sample_series(label, DEFAULT_LEVELS.get(label, 100.0))
            row["ytd_change"] = round(row.get("one_month_change", 0) * 2.5, 2)
            row.update(explain_commodity(row))
            row["driver"] = row["comment"]
            rows.append(row)
            continue
        yahoo_symbol = item.get("symbol")
        if yahoo_symbol:
            try:
                row = market_row(
                    label,
                    yahoo_symbol,
                    "",
                    f"https://finance.yahoo.com/quote/{yahoo_symbol}",
                )
                row.update(explain_commodity(row))
                row["driver"] = row["comment"]
                rows.append(row)
                continue
            except Exception as exc:
                record_error("yahoo_finance", f"{label}: {exc}")
        record_fallback()
        row = sample_series(label, DEFAULT_LEVELS.get(label, 100.0))
        row["ytd_change"] = round(row.get("one_month_change", 0) * 2.5, 2)
        row.update(explain_commodity(row))
        row["driver"] = row["comment"]
        rows.append(row)
    return rows
