from __future__ import annotations

import os
from urllib.parse import urlsplit

import requests

from src.fetchers.provider_audit import (
    record_error,
    record_tiingo_request,
    record_tiingo_status,
)
from src.processing.article_enrichment import enrich_article
from src.processing.clean import clean_text
from src.utils.dates import is_within_days, parse_date


TIINGO_NEWS_URL = "https://api.tiingo.com/tiingo/news"
KNOWN_SOURCE_NAMES = {
    "reuters.com": "Reuters",
    "ft.com": "Financial Times",
    "cnbc.com": "CNBC",
    "seekingalpha.com": "Seeking Alpha",
    "bloomberg.com": "Bloomberg",
}


def fetch_tiingo_articles(config: dict | None, lookback_days: int = 7) -> list[dict]:
    settings = config or {}
    api_key = os.getenv("TIINGO_API_KEY")
    if not api_key:
        record_tiingo_status("missing_api_key")
        return []
    if not _feature_enabled(settings):
        record_tiingo_status("disabled")
        return []
    if not _env_flag("TIINGO_ALLOW_PERSISTENCE", default=False):
        record_tiingo_status("blocked_by_persistence_guard")
        return []

    max_results = _bounded_int(settings.get("max_results_per_request", 25), 1, 100)
    max_requests = _bounded_int(settings.get("max_requests", 2), 1, 10)
    max_summary_chars = _bounded_int(settings.get("max_summary_chars", 1200), 200, 4000)
    timeout = _bounded_int(settings.get("request_timeout_seconds", 15), 1, 60)
    sort_by = settings.get("sort_by", "publishedDate")
    if sort_by not in {"publishedDate", "crawlDate"}:
        sort_by = "publishedDate"

    articles: list[dict] = []
    seen_urls: set[str] = set()
    request_specs = _request_specs(settings)[:max_requests]
    for request_name, tickers in request_specs:
        params: dict[str, str | int] = {"limit": max_results, "sortBy": sort_by}
        if tickers:
            params["tickers"] = ",".join(tickers)
        try:
            response = requests.get(
                TIINGO_NEWS_URL,
                headers={
                    "Authorization": f"Token {api_key}",
                    "Accept": "application/json",
                },
                params=params,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError("Tiingo News returned a non-list payload")
        except (requests.RequestException, ValueError) as exc:
            record_error("tiingo", f"{request_name}: {exc}")
            record_tiingo_status("provider_error")
            continue

        request_count = 0
        for item in payload:
            article = _article_from_item(item, lookback_days, max_summary_chars)
            if not article or article["url"] in seen_urls:
                continue
            articles.append(article)
            seen_urls.add(article["url"])
            request_count += 1
        record_tiingo_request(request_name, request_count)

    return articles


def _article_from_item(item: object, lookback_days: int, max_summary_chars: int) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = clean_text(item.get("title"))
    url = clean_text(item.get("url"))
    published_at = parse_date(item.get("publishedDate") or item.get("crawlDate"))
    if not title or not _is_http_url(url) or not is_within_days(published_at, lookback_days):
        return None

    tickers = _clean_list(item.get("tickers"), uppercase=True)
    tags = _clean_list(item.get("tags"))
    summary = clean_text(item.get("description"))[:max_summary_chars]
    source = _source_name(item.get("source"), url)
    article = enrich_article(
        {
            "title": title,
            "source": source,
            "published_at": published_at,
            "date": published_at.date().isoformat() if published_at else "",
            "url": url,
            "summary": summary,
            "tickers": tickers,
            "tags": tags,
            "discovery_provider": "Tiingo",
            "source_quality_provider": "Tiingo",
        }
    )
    article["entities"] = list(dict.fromkeys([*article.get("entities", []), *tickers]))
    return article


def _request_specs(settings: dict) -> list[tuple[str, list[str]]]:
    requests_to_run: list[tuple[str, list[str]]] = []
    if settings.get("include_general_feed", True):
        requests_to_run.append(("Latest Financial News", []))
    for index, group in enumerate(settings.get("ticker_groups") or [], start=1):
        if isinstance(group, dict):
            name = clean_text(group.get("name")) or f"Ticker Group {index}"
            tickers = _clean_list(group.get("tickers"), uppercase=True)
        else:
            name = f"Ticker Group {index}"
            tickers = _clean_list(group, uppercase=True)
        if tickers:
            requests_to_run.append((name, tickers[:50]))
    return requests_to_run


def _source_name(value: object, article_url: str) -> str:
    source = clean_text(value).lower().removeprefix("www.")
    if not source:
        source = urlsplit(article_url).netloc.lower().removeprefix("www.")
    return KNOWN_SOURCE_NAMES.get(source, source or "Tiingo")


def _clean_list(value: object, uppercase: bool = False) -> list[str]:
    if isinstance(value, str):
        values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        return []
    cleaned = [clean_text(item) for item in values]
    if uppercase:
        cleaned = [item.upper() for item in cleaned]
    return list(dict.fromkeys(item for item in cleaned if item))


def _is_http_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme in {"http", "https"} and bool(parts.netloc)


def _feature_enabled(settings: dict) -> bool:
    env_value = os.getenv("TIINGO_NEWS_ENABLED")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(settings.get("enabled", True))


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, maximum))
