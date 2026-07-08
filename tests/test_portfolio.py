from src.portfolio.exposure import portfolio_summary
from src.portfolio.relevance import portfolio_relevance_score


def test_portfolio_summary_groups_exposure():
    holdings = [
        {
            "holding": "A",
            "asset_class": "equity",
            "region": "US",
            "sector": "Technology",
            "currency": "USD",
            "weight": 0.6,
        },
        {
            "holding": "B",
            "asset_class": "bond",
            "region": "US",
            "sector": "Credit",
            "currency": "USD",
            "weight": 0.4,
        },
    ]
    summary = portfolio_summary(holdings)
    assert summary["total_weight"] == 1.0
    assert summary["region"][0]["name"] == "US"


def test_portfolio_relevance_scores_matching_article():
    holdings = [
        {
            "holding": "Tech ETF",
            "asset_class": "equity",
            "region": "United States",
            "sector": "Technology",
            "currency": "USD",
            "weight": 0.5,
        }
    ]
    article = {
        "title": "USD and technology shares move higher",
        "summary": "US equities rally",
        "category": "markets",
    }
    assert portfolio_relevance_score(article, holdings) > 0
