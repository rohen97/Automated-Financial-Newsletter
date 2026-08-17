from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from src.fetchers.provider_audit import record_error, record_ft_query
from src.processing.article_enrichment import enrich_article
from src.processing.clean import clean_text
from src.utils.dates import is_within_days, parse_date


FT_SEARCH_URL = "https://api.ft.com/content/search/v1"
FT_SEARCH_ASPECTS = ["title", "lifecycle", "location", "summary"]


def fetch_financial_times_articles(config: dict | None, lookback_days: int = 7) -> list[dict]:
    settings = config or {}
    api_key = os.getenv("FT_API_KEY")
    if not api_key or not settings.get("enabled", True):
        return []

    max_results = _bounded_int(settings.get("max_results_per_query", 15), minimum=1, maximum=100)
    timeout = _bounded_int(settings.get("request_timeout_seconds", 20), minimum=1, maximum=60)
    since = datetime.now(timezone.utc) - timedelta(days=max(1, lookback_days))
    since_text = since.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    articles: list[dict] = []
    seen_urls: set[str] = set()

    for query_config in _query_configs(settings):
        query = clean_text(query_config.get("query"))
        if not query:
            continue
        label = clean_text(query_config.get("name")) or query
        request_body = {
            "queryString": f"({query}) AND lastPublishDateTime:>{since_text}",
            "queryContext": {"curations": ["ARTICLES"]},
            "resultContext": {
                "maxResults": max_results,
                "offset": 0,
                "aspects": FT_SEARCH_ASPECTS,
                "sortField": "lastPublishDateTime",
                "sortOrder": "DESC",
            },
        }
        try:
            response = requests.post(
                FT_SEARCH_URL,
                headers={
                    "X-Api-Key": api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=request_body,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            record_error("financial_times", f"{label}: {exc}")
            continue

        query_count = 0
        for item in _search_results(payload):
            article = _article_from_result(item, query_config, lookback_days)
            if not article or article["url"] in seen_urls:
                continue
            articles.append(article)
            seen_urls.add(article["url"])
            query_count += 1
        record_ft_query(query, query_count)

    return articles


def _article_from_result(item: dict, query_config: dict, lookback_days: int) -> dict | None:
    title_value = item.get("title") or {}
    title = clean_text(title_value.get("title") if isinstance(title_value, dict) else title_value)
    lifecycle = item.get("lifecycle") or {}
    published_at = parse_date(
        lifecycle.get("initialPublishDateTime") or lifecycle.get("lastPublishDateTime")
    )
    location = item.get("location") or {}
    raw_url = clean_text(location.get("uri"))
    if not raw_url and item.get("id"):
        raw_url = f"https://www.ft.com/content/{item['id']}"
    if not title or not raw_url or not is_within_days(published_at, lookback_days):
        return None

    summary_value = item.get("summary") or {}
    summary = clean_text(summary_value.get("excerpt") if isinstance(summary_value, dict) else summary_value)
    article = {
        "title": title,
        "source": "Financial Times",
        "published_at": published_at,
        "date": published_at.date().isoformat() if published_at else "",
        "url": _with_ft_campaign(raw_url),
        "summary": summary,
    }
    if query_config.get("category"):
        article["category"] = query_config["category"]
    if query_config.get("region"):
        article["region"] = query_config["region"]
    return enrich_article(article)


def _search_results(payload: dict) -> list[dict]:
    items: list[dict] = []
    for block in payload.get("results") or []:
        if not isinstance(block, dict):
            continue
        nested = block.get("results")
        if isinstance(nested, list):
            items.extend(item for item in nested if isinstance(item, dict))
        elif block.get("id"):
            items.append(block)
    return items


def _query_configs(settings: dict) -> list[dict]:
    configured = settings.get("queries") or []
    queries = []
    for item in configured:
        if isinstance(item, str):
            queries.append({"query": item})
        elif isinstance(item, dict):
            queries.append(item)
    return queries


def _with_ft_campaign(url: str) -> str:
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if any(key.lower() == "ftcamp" for key, _ in query):
        return url

    source = _campaign_token(os.getenv("FT_API_TRACKING_SOURCE", "email"), "email")
    organisation = _campaign_token(os.getenv("FT_API_ORG_NAME", "WolfResearch"), "WolfResearch")
    campaign = f"engage/CAPI/{source}/Channel_{organisation}//B2B"
    query.append(("FTCamp", campaign))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, safe="/"), parts.fragment))


def _campaign_token(value: str | None, fallback: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "")).strip("_")
    return token or fallback


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, maximum))
