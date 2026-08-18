from __future__ import annotations

import re
from collections import defaultdict
from typing import Any


_AUDIT: dict[str, Any] = {
    "providers_used": set(),
    "fred_series_fetched": [],
    "alpha_vantage_symbols_fetched": [],
    "marketaux_queries_run": [],
    "ft_queries_run": [],
    "ft_articles_fetched": 0,
    "tiingo_requests_run": [],
    "tiingo_articles_fetched": 0,
    "tiingo_status": "not_configured",
    "google_news_queries_run": [],
    "rss_sources_fetched": [],
    "gmail_messages_ingested": 0,
    "fallback_source_count": 0,
    "errors": [],
}


def reset_provider_audit() -> None:
    _AUDIT["providers_used"] = set()
    _AUDIT["fred_series_fetched"] = []
    _AUDIT["alpha_vantage_symbols_fetched"] = []
    _AUDIT["marketaux_queries_run"] = []
    _AUDIT["ft_queries_run"] = []
    _AUDIT["ft_articles_fetched"] = 0
    _AUDIT["tiingo_requests_run"] = []
    _AUDIT["tiingo_articles_fetched"] = 0
    _AUDIT["tiingo_status"] = "not_configured"
    _AUDIT["google_news_queries_run"] = []
    _AUDIT["rss_sources_fetched"] = []
    _AUDIT["gmail_messages_ingested"] = 0
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


def record_ft_query(query: str, article_count: int = 0) -> None:
    if query not in _AUDIT["ft_queries_run"]:
        _AUDIT["ft_queries_run"].append(query)
    _AUDIT["ft_articles_fetched"] += max(0, article_count)
    record_provider("financial_times")


def record_tiingo_request(request_name: str, article_count: int = 0) -> None:
    if request_name not in _AUDIT["tiingo_requests_run"]:
        _AUDIT["tiingo_requests_run"].append(request_name)
    _AUDIT["tiingo_articles_fetched"] += max(0, article_count)
    _AUDIT["tiingo_status"] = "ok"
    record_provider("tiingo")


def record_tiingo_status(status: str) -> None:
    _AUDIT["tiingo_status"] = status


def record_google_news_query(query: str) -> None:
    if query not in _AUDIT["google_news_queries_run"]:
        _AUDIT["google_news_queries_run"].append(query)
    record_provider("google_news")


def record_rss_source(source: str) -> None:
    if source not in _AUDIT["rss_sources_fetched"]:
        _AUDIT["rss_sources_fetched"].append(source)
    record_provider("rss")


def record_gmail_messages(count: int) -> None:
    if count <= 0:
        return
    _AUDIT["gmail_messages_ingested"] += count
    record_provider("gmail_mcp")


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
    text = re.sub(r"(?i)(token=)[^&\s]+", r"\1***", text)
    text = re.sub(r"(?i)(X-Api-Key[:=]\s*)[^\s,}]+", r"\1***", text)
    text = re.sub(r"(?i)(Authorization[:=]\s*Token\s+)[^\s,}]+", r"\1***", text)
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._\-]+", r"\1***", text)
    text = re.sub(r"(?i)(Token\s+)[A-Za-z0-9._\-]+", r"\1***", text)
    return text


def provider_audit_snapshot() -> dict[str, Any]:
    snapshot = dict(_AUDIT)
    snapshot["providers_used"] = sorted(snapshot["providers_used"])
    return snapshot


def source_counts(payload: Any) -> dict[str, int]:
    counts = defaultdict(int)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if "name" in value and "url" in value and not isinstance(value.get("source"), (dict, str)):
                name = str(value.get("name", ""))
                url = str(value.get("url", ""))
                if name == "Sample Data" or "Fallback source" in name or "example.com/wolf-research" in url:
                    counts["fallback_source_count"] += 1
                elif url:
                    counts["real_source_url_count"] += 1
            source = value.get("source")
            if isinstance(source, str) and value.get("url"):
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
