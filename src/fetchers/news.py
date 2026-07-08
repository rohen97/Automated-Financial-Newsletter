from __future__ import annotations

import os

import requests

from src.fetchers.base import sample_article
from src.fetchers.provider_audit import record_error, record_fallback, record_marketaux_query
from src.processing.clean import clean_text
from src.utils.dates import is_within_days, parse_date
from src.utils.env import live_fetch_enabled
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)
MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"


def fetch_rss_articles(feeds: list[dict], lookback_days: int = 7) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        LOGGER.warning("feedparser is unavailable; using fallback news.")
        return []

    articles: list[dict] = []
    for feed in feeds:
        parsed = feedparser.parse(feed.get("url"))
        for entry in parsed.entries:
            published_at = parse_date(entry.get("published") or entry.get("updated"))
            if not is_within_days(published_at, lookback_days):
                continue
            articles.append(
                {
                    "title": clean_text(entry.get("title")),
                    "source": feed.get("name", parsed.feed.get("title", "RSS")),
                    "published_at": published_at,
                    "date": published_at.date().isoformat() if published_at else "",
                    "url": entry.get("link", feed.get("url")),
                    "summary": clean_text(entry.get("summary") or entry.get("description")),
                    "category": feed.get("category", "markets"),
                }
            )
    return articles


def fallback_articles() -> list[dict]:
    return [
        sample_article("Central bank policy remains the key macro risk for portfolios", "macro", days_ago=1),
        sample_article("USD strength keeps Asian FX volatility in focus", "fx", days_ago=1),
        sample_article("Oil markets balance supply discipline against softer demand signals", "commodities", days_ago=2),
        sample_article("Private equity exits remain selective as valuation gaps persist", "private_markets", days_ago=2),
        sample_article("Technology and financials lead the sector performance split", "sectors", days_ago=3),
        sample_article("Investors watch inflation data and central bank guidance this week", "watchlist", days_ago=1),
    ]


def fetch_marketaux_articles(queries: list[str], lookback_days: int = 7, limit_per_query: int = 3) -> list[dict]:
    api_key = os.getenv("MARKETAUX_API_KEY")
    if not api_key:
        return []
    articles: list[dict] = []
    seen_urls = set()
    for query in queries:
        try:
            response = requests.get(
                MARKETAUX_URL,
                params={
                    "api_token": api_key,
                    "search": query,
                    "language": "en",
                    "limit": limit_per_query,
                    "sort": "published_desc",
                },
                timeout=20,
            )
            response.raise_for_status()
            payload = response.json()
            record_marketaux_query(query)
            for item in payload.get("data", []):
                url = item.get("url") or ""
                if not url or url in seen_urls:
                    continue
                published_at = parse_date(item.get("published_at"))
                if not is_within_days(published_at, lookback_days):
                    continue
                source_name = (item.get("source") or "").strip() or "Marketaux"
                articles.append(
                    {
                        "title": clean_text(item.get("title", "")),
                        "source": source_name,
                        "published_at": published_at,
                        "date": published_at.date().isoformat() if published_at else "",
                        "url": url,
                        "summary": clean_text(item.get("description") or item.get("snippet") or ""),
                        "category": _category_from_query(query),
                        "region": _region_from_query(query),
                    }
                )
                seen_urls.add(url)
        except Exception as exc:
            record_error("marketaux", f"{query}: {exc}")
    return articles


def _category_from_query(query: str) -> str:
    text = query.lower()
    if any(term in text for term in ("private equity", "private credit", "private markets")):
        return "private_markets"
    if "commodity" in text or "oil" in text or "gold" in text:
        return "commodities"
    if "fx" in text or "currency" in text or "usd" in text:
        return "fx"
    if "macro" in text or "inflation" in text or "central bank" in text:
        return "macro"
    return "markets"


def _region_from_query(query: str) -> str:
    text = query.lower()
    if text.startswith("us "):
        return "US"
    if "europe" in text or "ecb" in text:
        return "EU"
    if text.startswith("uk "):
        return "UK"
    if "asia pacific" in text or "china singapore" in text:
        return "APAC"
    if "emea" in text:
        return "EMEA"
    if "global" in text:
        return "Global"
    return ""


def fetch_news(sources_config: dict, lookback_days: int = 7) -> list[dict]:
    marketaux_queries = [
        "US markets Federal Reserve inflation",
        "Europe markets ECB growth",
        "UK markets Bank of England",
        "Asia Pacific markets China Singapore",
        "EMEA markets credit geopolitical risk",
        "global markets macro rates",
        "FX USD currency markets",
        "commodities oil gold copper natural gas",
        "private equity private credit fundraising",
        "Alibaba BMW Allianz Singapore Airlines Sembcorp RWE Microsoft Alphabet Amazon Apple KFW",
    ]
    marketaux_articles = fetch_marketaux_articles(marketaux_queries, lookback_days)
    if marketaux_articles:
        return marketaux_articles
    if not live_fetch_enabled(sources_config):
        fallback = fallback_articles()
        record_fallback(len(fallback))
        return fallback
    feeds = []
    for category, items in (sources_config.get("rss_feeds") or {}).items():
        for item in items:
            feeds.append({**item, "category": category})
    articles = fetch_rss_articles(feeds, lookback_days)
    if articles:
        return articles
    fallback = fallback_articles()
    record_fallback(len(fallback))
    return fallback
