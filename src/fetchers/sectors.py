from __future__ import annotations


def fetch_sector_scoreboard(tickers_config: dict) -> list[dict]:
    rows = []
    for idx, item in enumerate(tickers_config.get("sectors", [])):
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
