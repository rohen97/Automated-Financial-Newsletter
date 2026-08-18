from src.fetchers import news
from src.utils.io import load_yaml


def test_public_news_sources_use_supported_feed_or_metadata_discovery():
    config = load_yaml("config/sources.yaml")
    feeds = [
        feed
        for category_feeds in config["rss_feeds"].values()
        for feed in category_feeds
    ]
    feed_urls = {feed["url"] for feed in feeds}

    assert "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain" in feed_urls
    assert "https://feeds.content.dowjones.io/public/rss/RSSWorldNews" in feed_urls
    assert "https://feeds.content.dowjones.io/public/rss/mw_topstories" in feed_urls
    assert "https://feeds.content.dowjones.io/public/rss/mw_marketpulse" in feed_urls
    assert all("feeds.reuters.com" not in url for url in feed_urls)

    discovery = {item["name"]: item for item in config["google_news_queries"]}
    assert "site:reuters.com/markets" in discovery["Reuters Markets via Google News"]["query"]
    assert "site:finance.yahoo.com/news" in discovery["Yahoo Finance via Google News"]["query"]
    assert "site:morningstar.com/markets" in discovery["Morningstar Markets via Google News"]["query"]
    assert config["rss_max_entries_per_feed"] == 30
    assert config["google_news_max_entries_per_query"] == 20


def test_google_news_discovery_applies_per_query_cap(monkeypatch):
    captured = {}

    def fake_fetch(feeds, lookback_days):
        captured["feeds"] = feeds
        captured["lookback_days"] = lookback_days
        return []

    monkeypatch.setattr(news, "fetch_rss_articles", fake_fetch)

    news.fetch_google_news_articles(
        [{"name": "Reuters", "query": "site:reuters.com markets"}],
        lookback_days=5,
        max_entries_per_query=7,
    )

    assert captured["lookback_days"] == 5
    assert captured["feeds"][0]["max_entries"] == 7
    assert captured["feeds"][0]["region"] == ""
