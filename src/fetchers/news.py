from __future__ import annotations

import os
import time
from urllib.parse import quote_plus

import requests

from src.fetchers.base import sample_article
from src.fetchers.financial_times import fetch_financial_times_articles
from src.fetchers.gmail_digest import load_gmail_digest
from src.fetchers.tiingo import fetch_tiingo_articles
from src.fetchers.provider_audit import (
    record_error,
    record_fallback,
    record_google_news_query,
    record_marketaux_query,
    record_rss_source,
)
from src.processing.clean import clean_text
from src.processing.article_enrichment import enrich_article
from src.utils.dates import is_within_days, parse_date
from src.utils.env import live_fetch_enabled
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)
MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
REQUEST_HEADERS = {
    "User-Agent": "WolfResearchNewsletter/1.0 (+internal research digest)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def fetch_rss_articles(feeds: list[dict], lookback_days: int = 7) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        LOGGER.warning("feedparser is unavailable; using fallback news.")
        return []

    articles: list[dict] = []
    for feed in feeds:
        feed_url = feed.get("url")
        if not feed_url:
            continue
        try:
            response = requests.get(feed_url, headers=REQUEST_HEADERS, timeout=20)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
        except Exception as exc:
            record_error("rss", f"{feed.get('name', feed_url)}: {exc}")
            continue
        feed_articles = 0
        for entry in parsed.entries:
            published_at = parse_date(entry.get("published") or entry.get("updated"))
            if not is_within_days(published_at, lookback_days):
                continue
            entry_source = entry.get("source") or {}
            source_name = feed.get("name", parsed.feed.get("title", "RSS"))
            if feed.get("discover_source"):
                source_name = entry_source.get("title") or source_name
            articles.append(
                enrich_article(
                    {
                    "title": clean_text(entry.get("title")),
                    "source": source_name,
                    "published_at": published_at,
                    "date": published_at.date().isoformat() if published_at else "",
                    "url": entry.get("link", feed.get("url")),
                    "summary": clean_text(entry.get("summary") or entry.get("description")),
                    "category": feed.get("category", "markets"),
                    "region": feed.get("region", ""),
                    }
                )
            )
            feed_articles += 1
        if feed_articles:
            record_rss_source(str(feed.get("name", feed_url)))
    return articles


def fetch_google_news_articles(queries: list[dict], lookback_days: int = 7) -> list[dict]:
    feeds = []
    for item in queries:
        query = clean_text(item.get("query"))
        if not query:
            continue
        feeds.append(
            {
                "name": item.get("name", "Google News"),
                "url": (
                    f"{GOOGLE_NEWS_RSS_URL}?q={quote_plus(query)}"
                    "&hl=en-US&gl=US&ceid=US:en"
                ),
                "category": item.get("category", "markets"),
                "region": item.get("region", ""),
                "discover_source": True,
            }
        )
        record_google_news_query(query)
    return fetch_rss_articles(feeds, lookback_days)


def fallback_articles() -> list[dict]:
    return [
        sample_article("Central bank policy remains the key macro risk for portfolios", "macro", days_ago=1),
        sample_article("USD strength keeps Asian FX volatility in focus", "fx", days_ago=1),
        sample_article("Oil markets balance supply discipline against softer demand signals", "commodities", days_ago=2),
        sample_article("Private equity exits remain selective as valuation gaps persist", "private_markets", days_ago=2),
        sample_article("Technology and financials lead the sector performance split", "sectors", days_ago=3),
        sample_article("Investors watch inflation data and central bank guidance this week", "watchlist", days_ago=1),
    ]


def fetch_marketaux_articles(
    queries: list[str],
    lookback_days: int = 7,
    limit_per_query: int = 3,
    max_seconds: int = 80,
) -> list[dict]:
    api_key = os.getenv("MARKETAUX_API_KEY")
    if not api_key:
        return []
    articles: list[dict] = []
    seen_urls = set()
    started_at = time.monotonic()
    consecutive_failures = 0
    for query in queries:
        if time.monotonic() - started_at >= max_seconds:
            record_error("marketaux", f"Fetch budget reached after {max_seconds} seconds")
            break
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
                timeout=12,
            )
            response.raise_for_status()
            payload = response.json()
            consecutive_failures = 0
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
                    enrich_article(
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
                )
                seen_urls.add(url)
        except Exception as exc:
            record_error("marketaux", f"{query}: {exc}")
            consecutive_failures += 1
            if consecutive_failures >= 3:
                record_error("marketaux", "Stopped after three consecutive provider failures")
                break
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
    if os.getenv("PYTEST_CURRENT_TEST"):
        fallback = fallback_articles()
        record_fallback(len(fallback))
        return fallback

    default_marketaux_queries = [
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
        "Singapore Airlines SATS oil travel demand",
        "Alibaba China internet ecommerce regulation",
        "Allianz BMW RWE Sanofi Europe rates growth",
        "private equity exits secondaries LP liquidity",
    ]

    marketaux_queries = list(dict.fromkeys(sources_config.get("marketaux_queries") or default_marketaux_queries))
    marketaux_queries = marketaux_queries[: int(sources_config.get("marketaux_max_queries", 12))]

    articles = load_gmail_digest(sources_config)
    ft_articles: list[dict] = []
    if os.getenv("FT_API_KEY"):
        ft_articles = fetch_financial_times_articles(sources_config.get("ft_api") or {}, lookback_days)
        articles.extend(ft_articles)
    if os.getenv("TIINGO_API_KEY"):
        articles.extend(fetch_tiingo_articles(sources_config.get("tiingo_news") or {}, lookback_days))
    if os.getenv("MARKETAUX_API_KEY"):
        articles.extend(
            fetch_marketaux_articles(
                marketaux_queries,
                lookback_days,
                max_seconds=int(sources_config.get("marketaux_fetch_budget_seconds", 80)),
            )
        )

    if not live_fetch_enabled(sources_config):
        if articles:
            return articles
        fallback = fallback_articles()
        record_fallback(len(fallback))
        return fallback

    feeds = []
    for category, items in (sources_config.get("rss_feeds") or {}).items():
        for item in items:
            if ft_articles and str(item.get("name", "")).lower().startswith("financial times"):
                continue
            feeds.append({**item, "category": category})
    articles.extend(fetch_rss_articles(feeds, lookback_days))
    articles.extend(fetch_google_news_articles(sources_config.get("google_news_queries") or [], lookback_days))
    if articles:
        return articles
    fallback = fallback_articles()
    record_fallback(len(fallback))
    return fallback
