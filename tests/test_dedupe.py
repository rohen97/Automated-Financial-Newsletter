from hashlib import sha256
import time

from src.processing.dedupe import dedupe_articles


def test_dedupe_by_url_and_similar_title():
    articles = [
        {"title": "Fed keeps rates in focus", "url": "https://example.com/1"},
        {"title": "Fed keeps rates in focus", "url": "https://example.com/1"},
        {"title": "Fed keeps rates firmly in focus", "url": "https://example.com/2"},
    ]
    assert len(dedupe_articles(articles, threshold=0.80)) == 1


def test_dedupe_avoids_all_pairs_work_for_unique_titles():
    articles = [
        {
            "title": sha256(str(index).encode()).hexdigest(),
            "url": f"https://example.com/{index}",
        }
        for index in range(400)
    ]

    started = time.perf_counter()
    result = dedupe_articles(articles)

    assert len(result) == 400
    assert time.perf_counter() - started < 1.5
