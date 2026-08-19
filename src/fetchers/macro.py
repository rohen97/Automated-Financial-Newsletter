from __future__ import annotations

import os
from datetime import date, timedelta

import requests

from src.fetchers.provider_audit import record_error, record_fallback, record_fred_series


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
SERIES = [
    ("DFF", "US policy rate", "Policy rates remain central to discount-rate sensitivity."),
    ("DGS10", "US 10Y yield", "Long-end yields drive duration, equity multiple, and credit repricing."),
    ("CPIAUCSL", "US CPI", "Inflation surprises drive cross-asset repricing."),
    ("UNRATE", "US unemployment rate", "Labour market momentum informs Fed reaction-function risk."),
    ("NFCI", "US financial conditions", "Financial conditions frame risk appetite and credit transmission."),
]


def _format_value(series_id: str, value: float) -> str:
    if series_id in {"DFF", "DGS10", "UNRATE"}:
        return f"{value:.2f}%"
    return f"{value:.2f}"


def _observation_snapshot(series_id: str, observations: list[dict]) -> dict:
    usable = []
    for item in observations:
        raw_value = item.get("value")
        observed_at = item.get("date")
        if raw_value in {None, "."} or not observed_at:
            continue
        usable.append(
            {
                "date": date.fromisoformat(observed_at),
                "date_display": observed_at,
                "value": float(raw_value),
            }
        )
    if not usable:
        raise ValueError(f"No usable FRED observation for {series_id}")

    usable.sort(key=lambda item: item["date"], reverse=True)
    latest = usable[0]
    reference_date = latest["date"] - timedelta(days=7)
    reference = next(
        (item for item in usable[1:] if item["date"] <= reference_date),
        usable[-1] if len(usable) > 1 else latest,
    )
    return {
        "value": _format_value(series_id, latest["value"]),
        "value_numeric": latest["value"],
        "observed_at": latest["date_display"],
        "reference_value_numeric": reference["value"],
        "reference_observed_at": reference["date_display"],
        "weekly_change": round(latest["value"] - reference["value"], 6),
    }


def _fetch_latest_fred(series_id: str, api_key: str) -> dict:
    start = (date.today() - timedelta(days=120)).isoformat()
    response = requests.get(
        FRED_OBSERVATIONS_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start,
            "sort_order": "desc",
            "limit": 10,
        },
        timeout=15,
    )
    response.raise_for_status()
    return _observation_snapshot(series_id, response.json().get("observations", []))


def fetch_macro_data() -> list[dict]:
    fred_key = os.getenv("FRED_API_KEY")
    rows = []
    for series_id, label, comment in SERIES:
        if fred_key:
            try:
                observation = _fetch_latest_fred(series_id, fred_key)
                record_fred_series(series_id)
                rows.append(
                    {
                        "series_id": series_id,
                        "indicator": label,
                        **observation,
                        "comment": f"{comment} Latest FRED observation: {observation['observed_at']}.",
                        "source": {"name": "FRED", "url": f"https://fred.stlouisfed.org/series/{series_id}"},
                    }
                )
                continue
            except Exception as exc:
                record_error("fred", f"{series_id}: {exc}")
        record_fallback()
        rows.append(
            {
                "series_id": series_id,
                "indicator": label,
                "value": "fallback",
                "comment": comment,
                "source": {"name": "Sample Data", "url": "https://example.com/wolf-research/fred-fallback"},
            }
        )
    return rows
