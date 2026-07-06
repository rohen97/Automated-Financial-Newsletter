from src.processing.dedupe import dedupe_articles


def test_dedupe_by_url_and_similar_title():
    articles = [
        {"title": "Fed keeps rates in focus", "url": "https://example.com/1"},
        {"title": "Fed keeps rates in focus", "url": "https://example.com/1"},
        {"title": "Fed keeps rates firmly in focus", "url": "https://example.com/2"},
    ]
    assert len(dedupe_articles(articles, threshold=0.80)) == 1
