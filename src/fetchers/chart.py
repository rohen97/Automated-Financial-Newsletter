from __future__ import annotations

import os
from collections import OrderedDict
from datetime import date, timedelta

import requests

from src.fetchers.provider_audit import record_error, record_fallback, record_fred_series


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


def _format_index(value: float | None) -> str:
    return "--" if value is None else f"{value:,.0f}"


def _format_pct(value: float | None) -> str:
    return "--" if value is None else f"{value:+.2f}%"


def _fetch_sp500_observations(api_key: str) -> list[dict]:
    response = requests.get(
        FRED_OBSERVATIONS_URL,
        params={
            "series_id": "SP500",
            "api_key": api_key,
            "file_type": "json",
            "observation_start": (date.today() - timedelta(days=180)).isoformat(),
        },
        timeout=15,
    )
    response.raise_for_status()
    rows = []
    for item in response.json().get("observations", []):
        raw_value = item.get("value")
        if raw_value in {None, "."}:
            continue
        observed_at = date.fromisoformat(item["date"])
        rows.append({"date": observed_at, "value": float(raw_value)})
    return rows


def _weekly_closes(rows: list[dict]) -> list[dict]:
    grouped: OrderedDict[tuple[int, int], dict] = OrderedDict()
    for row in rows:
        iso_year, iso_week, _ = row["date"].isocalendar()
        grouped[(iso_year, iso_week)] = row
    return list(grouped.values())


def fetch_chart_of_the_week() -> dict:
    api_key = os.getenv("FRED_API_KEY")
    if api_key:
        try:
            weekly = _weekly_closes(_fetch_sp500_observations(api_key))
            if len(weekly) >= 10:
                record_fred_series("SP500")
                rows = []
                closes = [item["value"] for item in weekly]
                for idx, item in enumerate(weekly[-10:], start=len(weekly) - 10):
                    ma_values = closes[max(0, idx - 9) : idx + 1]
                    ma = sum(ma_values) / len(ma_values)
                    distance = ((item["value"] / ma) - 1) * 100 if ma else 0.0
                    rows.append(
                        {
                            "week": item["date"].isoformat(),
                            "close": item["value"],
                            "close_display": _format_index(item["value"]),
                            "moving_average": ma,
                            "moving_average_display": _format_index(ma),
                            "distance_pct": distance,
                            "distance_display": _format_pct(distance),
                            "bar_width": min(100, max(8, int(abs(distance) * 12))),
                        }
                    )
                latest = rows[-1]
                relation = "above" if latest["distance_pct"] >= 0 else "below"
                return {
                    "title": "Chart of the Week",
                    "subtitle": "S&P 500 vs 10-week moving average",
                    "takeaway": (
                        f"The S&P 500 is {latest['distance_display']} {relation} its 10-week moving average, "
                        "a simple gauge of medium-term trend discipline."
                    ),
                    "rows": rows,
                    "source": {"name": "FRED", "url": "https://fred.stlouisfed.org/series/SP500"},
                }
        except Exception as exc:
            record_error("fred", f"SP500 chart: {exc}")

    record_fallback()
    rows = [
        {"week": f"Week {idx}", "close_display": str(5000 + idx * 35), "moving_average_display": str(4940 + idx * 30), "distance_pct": 1.0 + idx * 0.1, "distance_display": f"+{1.0 + idx * 0.1:.2f}%", "bar_width": 18 + idx * 5}
        for idx in range(1, 11)
    ]
    return {
        "title": "Chart of the Week",
        "subtitle": "S&P 500 vs 10-week moving average",
        "takeaway": "The S&P 500 remains above its 10-week moving average in fallback mode.",
        "rows": rows,
        "source": {"name": "Sample Data", "url": "https://example.com/wolf-research/sp500-chart-fallback"},
    }
