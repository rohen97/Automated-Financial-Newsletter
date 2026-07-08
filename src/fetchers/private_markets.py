from __future__ import annotations

import os

from src.fetchers.base import sample_article
from src.fetchers.news import fetch_marketaux_articles, fetch_rss_articles
from src.fetchers.provider_audit import record_fallback
from src.utils.env import live_fetch_enabled


def fetch_private_markets_news(sources_config: dict, lookback_days: int = 7) -> list[dict]:
    marketaux_articles = fetch_marketaux_articles(
        ["private equity exits fundraising", "private credit direct lending fundraising", "venture capital private markets"],
        lookback_days,
        limit_per_query=3,
    )
    if marketaux_articles:
        return [{**article, "category": "private_markets"} for article in marketaux_articles]
    if not live_fetch_enabled(sources_config):
        record_fallback(2)
        return [
            sample_article("Private credit fundraising remains resilient", "private_markets", days_ago=1),
            sample_article("Exit markets show gradual reopening for high-quality assets", "private_markets", days_ago=2),
        ]
    feeds = sources_config.get("rss_feeds", {}).get("private_markets", [])
    articles = fetch_rss_articles([{**feed, "category": "private_markets"} for feed in feeds], lookback_days)
    if articles:
        return articles
    placeholders = []
    if not os.getenv("CRUNCHBASE_API_KEY"):
        placeholders.append(sample_article("Crunchbase integration placeholder active", "private_markets"))
        record_fallback()
    placeholders.extend(
        [
            sample_article("Private credit fundraising remains resilient", "private_markets", days_ago=1),
            sample_article("Exit markets show gradual reopening for high-quality assets", "private_markets", days_ago=2),
        ]
    )
    record_fallback(2)
    return placeholders
