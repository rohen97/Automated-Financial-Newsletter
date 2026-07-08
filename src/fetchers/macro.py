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
    if series_id in {"DFF", "DGS10", "UNRATE", "NFCI"}:
        return f"{value:.2f}%"
    return f"{value:.2f}"


def _fetch_latest_fred(series_id: str, api_key: str) -> tuple[str, str]:
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
    observations = response.json().get("observations", [])
    for item in observations:
        raw_value = item.get("value")
        if raw_value in {None, "."}:
            continue
        return _format_value(series_id, float(raw_value)), item.get("date", "")
    raise ValueError(f"No usable FRED observation for {series_id}")


def fetch_macro_data() -> list[dict]:
    fred_key = os.getenv("FRED_API_KEY")
    rows = []
    for series_id, label, comment in SERIES:
        if fred_key:
            try:
                value, observed_at = _fetch_latest_fred(series_id, fred_key)
                record_fred_series(series_id)
                rows.append(
                    {
                        "indicator": label,
                        "value": value,
                        "comment": f"{comment} Latest FRED observation: {observed_at}.",
                        "source": {"name": "FRED", "url": f"https://fred.stlouisfed.org/series/{series_id}"},
                    }
                )
                continue
            except Exception as exc:
                record_error("fred", f"{series_id}: {exc}")
        record_fallback()
        rows.append(
            {
                "indicator": label,
                "value": "fallback",
                "comment": comment,
                "source": {"name": "Sample Data", "url": "https://example.com/wolf-research/fred-fallback"},
            }
        )
    return rows
