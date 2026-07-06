from __future__ import annotations

import os

from src.fetchers.base import sample_article
from src.fetchers.news import fetch_rss_articles


def fetch_private_markets_news(sources_config: dict, lookback_days: int = 7) -> list[dict]:
    if not sources_config.get("live_fetch", False):
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
    placeholders.extend(
        [
            sample_article("Private credit fundraising remains resilient", "private_markets", days_ago=1),
            sample_article("Exit markets show gradual reopening for high-quality assets", "private_markets", days_ago=2),
        ]
    )
    return placeholders
