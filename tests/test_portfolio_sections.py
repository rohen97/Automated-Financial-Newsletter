from src.main import build_newsletter
from src.portfolio.equity import load_equity_holdings
from src.portfolio.portfolio_news import portfolio_watchlist


def test_portfolio_sections_are_present():
    newsletter = build_newsletter()
    sections = newsletter["sections"]
    assert "portfolio_snapshot" in sections
    assert "equity_holdings_monitor" in sections
    assert "chart_of_the_week" in sections
    assert "narrative_monitor" in sections
    assert "portfolio_linked_news" in sections
    assert "regional_headlines" in sections
    assert "portfolio_watchlist" in sections


def test_portfolio_watchlist_uses_current_holdings():
    watchlist = portfolio_watchlist(load_equity_holdings())
    text = " ".join(row["portfolio_relevance"] for row in watchlist["rows"])
    assert "Munich Re" in text
    assert "BASF" in text
    assert "ING" not in text
    assert "Allianz" not in text
