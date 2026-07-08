from __future__ import annotations

from src.fetchers.market_data import fetch_alpha_vantage_history, pct_change
from src.fetchers.provider_audit import record_error, record_fallback


def fetch_sector_scoreboard(tickers_config: dict) -> list[dict]:
    rows = []
    for idx, item in enumerate(tickers_config.get("sectors", [])):
        try:
            history = fetch_alpha_vantage_history("TIME_SERIES_DAILY", item["symbol"], outputsize="full")
            if history:
                last = history[-1]["close"]
                week_ref = history[-6]["close"] if len(history) >= 6 else history[0]["close"]
                month_ref = history[-22]["close"] if len(history) >= 22 else history[0]["close"]
                year_ref = history[0]["close"]
                one_week = pct_change(last, week_ref)
                one_month = pct_change(last, month_ref)
                ytd = pct_change(last, year_ref)
                rows.append(
                    {
                        "sector": item["label"],
                        "one_week": one_week,
                        "one_month": one_month,
                        "ytd": ytd,
                        "comment": "Outperforming" if one_week > 0 else "Under pressure" if one_week < 0 else "Stable",
                        "source": {"name": "Alpha Vantage", "url": f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={item['symbol']}"},
                    }
                )
                continue
        except Exception as exc:
            record_error("alpha_vantage", f"{item['label']}: {exc}")
            record_fallback()
        week = round((idx - 3) * 0.45, 2)
        month = round((idx - 2) * 0.9, 2)
        ytd = round(4.0 + idx * 1.1, 2)
        rows.append(
            {
                "sector": item["label"],
                "one_week": week,
                "one_month": month,
                "ytd": ytd,
                "comment": "Leadership broadening" if week >= 0 else "Near-term underperformance",
                "source": {"name": "Sample Data", "url": "https://example.com/wolf-research/sector-scoreboard"},
            }
        )
    return rows
