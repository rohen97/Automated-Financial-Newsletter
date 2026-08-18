from src.portfolio.portfolio_news import regional_headlines


def test_regional_headlines_filter_low_signal_items_and_diversify_sources():
    articles = [
        {
            "title": "Federal Reserve requests comment on a proposal",
            "source": "Federal Reserve",
            "category": "macro",
            "region": "US",
            "url": "https://example.test/administrative",
        },
        {
            "title": "US inflation reprices the rates outlook",
            "source": "Federal Reserve",
            "category": "macro",
            "region": "US",
            "url": "https://example.test/inflation",
        },
        {
            "title": "Wall Street weighs earnings and Treasury yields",
            "source": "CNBC",
            "category": "markets",
            "region": "US",
            "url": "https://example.test/wall-street",
        },
        {
            "title": "US banks prepare for tighter credit conditions",
            "source": "Federal Reserve",
            "category": "macro",
            "region": "US",
            "url": "https://example.test/credit",
        },
    ]

    section = regional_headlines(articles, max_per_region=3)
    us = next(item for item in section["regions"] if item["region"] == "US")

    assert [item["source"] for item in us["headlines"][:2]] == ["Federal Reserve", "CNBC"]
    assert all("requests comment" not in item["headline"].lower() for item in us["headlines"])
