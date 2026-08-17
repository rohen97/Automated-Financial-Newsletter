from __future__ import annotations

import os
from datetime import date, timedelta

import requests

from src.fetchers.provider_audit import record_error, record_fred_series


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


def fetch_fred_series(series_id: str, lookback_months: int, api_key: str | None = None) -> list[dict]:
    key = api_key or os.getenv("FRED_API_KEY")
    if not key:
        raise RuntimeError("FRED_API_KEY not configured.")
    start = date.today() - timedelta(days=max(lookback_months + 12, 13) * 31)
    response = requests.get(
        FRED_OBSERVATIONS_URL,
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "observation_start": start.isoformat(),
        },
        timeout=20,
    )
    response.raise_for_status()
    rows = clean_observations(response.json().get("observations", []))
    if not rows:
        raise RuntimeError(f"FRED returned no usable observations for {series_id}.")
    record_fred_series(series_id)
    cutoff = date.today() - timedelta(days=lookback_months * 31)
    return [row for row in rows if row["date"] >= cutoff]


def clean_observations(observations: list[dict]) -> list[dict]:
    rows = []
    for item in observations:
        raw_value = item.get("value")
        if raw_value in {None, "."}:
            continue
        try:
            rows.append({"date": date.fromisoformat(item["date"]), "value": float(raw_value)})
        except (TypeError, ValueError) as exc:
            record_error("fred", f"skipped malformed observation: {exc}")
    return sorted(rows, key=lambda row: row["date"])


def transform_series(rows: list[dict], transformation: str | None = None) -> list[dict]:
    if not transformation or transformation == "raw":
        return rows
    if transformation == "yoy_pct_change":
        return _year_over_year_pct_change(rows)
    if transformation == "mom_change":
        return _period_change(rows, 1, pct=False)
    if transformation == "difference":
        return _period_change(rows, 1, pct=False)
    if transformation == "z_score":
        return z_score_series(rows)
    raise ValueError(f"Unsupported FRED transformation: {transformation}")


def z_score_series(rows: list[dict], window: int = 52) -> list[dict]:
    output = []
    values = [row["value"] for row in rows]
    for idx, row in enumerate(rows):
        sample = values[max(0, idx - window + 1) : idx + 1]
        mean = sum(sample) / len(sample)
        variance = sum((value - mean) ** 2 for value in sample) / len(sample)
        std = variance**0.5
        output.append({"date": row["date"], "value": 0.0 if std == 0 else (row["value"] - mean) / std})
    return output


def _period_change(rows: list[dict], periods: int, pct: bool) -> list[dict]:
    output = []
    for idx in range(periods, len(rows)):
        previous = rows[idx - periods]["value"]
        current = rows[idx]["value"]
        if pct:
            value = ((current / previous) - 1) * 100 if previous else 0.0
        else:
            value = current - previous
        output.append({"date": rows[idx]["date"], "value": value})
    return output


def _year_over_year_pct_change(rows: list[dict]) -> list[dict]:
    """Calculate YoY change by date so daily and monthly inputs behave consistently."""
    from datetime import timedelta

    output = []
    prior_index = 0
    for current in rows:
        target = current["date"] - timedelta(days=365)
        while prior_index + 1 < len(rows) and rows[prior_index + 1]["date"] <= target:
            prior_index += 1
        previous = rows[prior_index]
        gap = (target - previous["date"]).days
        if previous["date"] > target or gap > 45:
            continue
        previous_value = previous["value"]
        value = ((current["value"] / previous_value) - 1) * 100 if previous_value else 0.0
        output.append({"date": current["date"], "value": value})
    return output
