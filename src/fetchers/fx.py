from __future__ import annotations

from src.fetchers.base import sample_series
from src.fetchers.market_data import alpha_market_row
from src.fetchers.provider_audit import record_error, record_fallback


DEFAULT_LEVELS = {"USD/SGD": 1.35, "AUD/USD": 0.66, "EUR/USD": 1.08, "DXY": 104.2}
ALPHA_SYMBOLS = {"USD/SGD": "USD/SGD", "AUD/USD": "AUD/USD", "EUR/USD": "EUR/USD", "DXY": "UUP"}
DRIVERS = {
    "USD/SGD": "USD rates / regional risk sentiment",
    "AUD/USD": "China growth / commodities beta",
    "EUR/USD": "ECB repricing",
    "DXY": "Broad USD momentum",
}


def fetch_fx_data(tickers_config: dict) -> list[dict]:
    rows = []
    for item in tickers_config.get("fx", []):
        label = item["label"]
        alpha_symbol = ALPHA_SYMBOLS.get(label)
        if alpha_symbol:
            try:
                function = "FX_DAILY" if "/" in alpha_symbol else "TIME_SERIES_DAILY"
                rows.append(
                    alpha_market_row(
                        label,
                        alpha_symbol,
                        DRIVERS.get(label, "Macro and rates momentum"),
                        f"https://www.alphavantage.co/query?function={function}",
                        function=function,
                    )
                )
                continue
            except Exception as exc:
                record_error("alpha_vantage", f"{label}: {exc}")
                record_fallback()
        row = sample_series(label, DEFAULT_LEVELS.get(label, 1.0))
        row["driver"] = DRIVERS.get(label, "Macro and rates momentum")
        rows.append(row)
    return rows
