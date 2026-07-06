from __future__ import annotations

from src.fetchers.base import sample_article
from src.processing.clean import clean_text
from src.utils.dates import is_within_days, parse_date
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


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


def fetch_news(sources_config: dict, lookback_days: int = 7) -> list[dict]:
    if not sources_config.get("live_fetch", False):
        return fallback_articles()
    feeds = []
    for category, items in (sources_config.get("rss_feeds") or {}).items():
        for item in items:
            feeds.append({**item, "category": category})
    articles = fetch_rss_articles(feeds, lookback_days)
    return articles or fallback_articles()
