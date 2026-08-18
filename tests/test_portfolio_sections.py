from src.main import build_newsletter


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
