from datetime import UTC, datetime

from src.processing.rank import importance_score, rank_articles, score_recency


def test_importance_score_formula():
    score = importance_score(
        source_quality=1.0,
        market_relevance=0.8,
        novelty=0.6,
        cross_asset_impact=0.4,
        recency=0.2,
    )
    assert score == 0.7


def test_recency_score_recent_is_higher():
    now = datetime(2026, 7, 6, tzinfo=UTC)
    assert score_recency(now, now) == 1


def test_rank_articles_orders_by_importance():
    articles = [
        {"title": "Minor company update", "summary": "", "source": "Sample Data", "url": "https://example.com/a"},
        {"title": "Fed rates and USD drive cross asset volatility", "summary": "inflation oil dollar", "source": "Reuters", "url": "https://example.com/b"},
    ]
    ranked = rank_articles(articles, {"Reuters": 1.0, "Sample Data": 0.2})
    assert ranked[0]["source"] == "Reuters"
