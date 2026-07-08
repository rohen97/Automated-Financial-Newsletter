from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


_AUDIT: dict[str, Any] = {
    "providers_used": set(),
    "fred_series_fetched": [],
    "alpha_vantage_symbols_fetched": [],
    "marketaux_queries_run": [],
    "fallback_source_count": 0,
    "errors": [],
}


def reset_provider_audit() -> None:
    _AUDIT["providers_used"] = set()
    _AUDIT["fred_series_fetched"] = []
    _AUDIT["alpha_vantage_symbols_fetched"] = []
    _AUDIT["marketaux_queries_run"] = []
    _AUDIT["fallback_source_count"] = 0
    _AUDIT["errors"] = []


def record_provider(provider: str) -> None:
    _AUDIT["providers_used"].add(provider)


def record_fred_series(series_id: str) -> None:
    if series_id not in _AUDIT["fred_series_fetched"]:
        _AUDIT["fred_series_fetched"].append(series_id)
    record_provider("fred")


def record_alpha_symbol(symbol: str) -> None:
    if symbol not in _AUDIT["alpha_vantage_symbols_fetched"]:
        _AUDIT["alpha_vantage_symbols_fetched"].append(symbol)
    record_provider("alpha_vantage")


def record_marketaux_query(query: str) -> None:
    if query not in _AUDIT["marketaux_queries_run"]:
        _AUDIT["marketaux_queries_run"].append(query)
    record_provider("marketaux")


def record_openai_used() -> None:
    record_provider("openai")


def record_fallback(count: int = 1) -> None:
    _AUDIT["fallback_source_count"] += count


def record_error(provider: str, message: str) -> None:
    _AUDIT["errors"].append({"provider": provider, "message": _sanitize_message(message)[:240]})


def _sanitize_message(message: str) -> str:
    text = str(message)
    text = re.sub(r"(?i)(api_token=)[^&\s]+", r"\1***", text)
    text = re.sub(r"(?i)(apikey=)[^&\s]+", r"\1***", text)
    text = re.sub(r"(?i)(api_key=)[^&\s]+", r"\1***", text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", text)
    return text


def provider_audit_snapshot() -> dict[str, Any]:
    snapshot = dict(_AUDIT)
    snapshot["providers_used"] = sorted(snapshot["providers_used"])
    return snapshot


def source_counts(payload: Any) -> dict[str, int]:
    counts = defaultdict(int)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            source = value.get("source")
            if isinstance(source, dict):
                name = str(source.get("name", ""))
                url = str(source.get("url", ""))
                if name == "Sample Data" or "example.com/wolf-research" in url:
                    counts["fallback_source_count"] += 1
                elif url:
                    counts["real_source_url_count"] += 1
            elif isinstance(source, str) and value.get("url"):
                url = str(value.get("url", ""))
                if "example.com/wolf-research" in url or source == "Fallback source":
                    counts["fallback_source_count"] += 1
                else:
                    counts["real_source_url_count"] += 1
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)
    return dict(counts)
