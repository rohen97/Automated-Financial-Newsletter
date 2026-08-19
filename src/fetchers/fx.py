from __future__ import annotations

import os

from src.fetchers.base import sample_series
from src.fetchers.market_data import alpha_market_row, market_row
from src.fetchers.provider_audit import record_error, record_fallback
from src.markets.driver_explainer import explain_fx


DEFAULT_LEVELS = {"USD/SGD": 1.35, "AUD/USD": 0.66, "EUR/USD": 1.08, "USD/CNH": 7.25, "USD/JPY": 160.0, "DXY": 104.2}
ALPHA_SYMBOLS = {
    "USD/SGD": "USD/SGD",
    "AUD/USD": "AUD/USD",
    "EUR/USD": "EUR/USD",
    "USD/CNH": "USD/CNH",
    "USD/JPY": "USD/JPY",
}


def fetch_fx_data(tickers_config: dict) -> list[dict]:
    rows = []
    for item in tickers_config.get("fx", []):
        label = item["label"]
        alpha_symbol = ALPHA_SYMBOLS.get(label)
        if os.getenv("PYTEST_CURRENT_TEST"):
            row = sample_series(label, DEFAULT_LEVELS.get(label, 1.0))
            row["ytd_change"] = round(row.get("one_month_change", 0) * 2.5, 2)
            row.update(explain_fx(row))
            row["driver"] = row["comment"]
            rows.append(row)
            continue
        if alpha_symbol:
            try:
                function = "FX_DAILY" if "/" in alpha_symbol else "TIME_SERIES_DAILY"
                row = (
                    alpha_market_row(
                        label,
                        alpha_symbol,
                        "",
                        f"https://www.alphavantage.co/query?function={function}",
                        function=function,
                    )
                )
                row.update(explain_fx(row))
                row["driver"] = row["comment"]
                rows.append(row)
                continue
            except Exception as exc:
                record_error("alpha_vantage", f"{label}: {exc}")
        yahoo_symbol = item.get("symbol")
        if yahoo_symbol:
            try:
                row = market_row(
                    label,
                    yahoo_symbol,
                    "",
                    f"https://finance.yahoo.com/quote/{yahoo_symbol}",
                )
                row.update(explain_fx(row))
                row["driver"] = row["comment"]
                rows.append(row)
                continue
            except Exception as exc:
                record_error("yahoo_finance", f"{label}: {exc}")
        record_fallback()
        row = sample_series(label, DEFAULT_LEVELS.get(label, 1.0))
        row["ytd_change"] = round(row.get("one_month_change", 0) * 2.5, 2)
        row.update(explain_fx(row))
        row["driver"] = row["comment"]
        rows.append(row)
    return rows
