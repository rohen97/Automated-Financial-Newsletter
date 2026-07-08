from __future__ import annotations

from src.analysis.story_selector import select_story_of_the_week
from src.llm.openai_sections import enhance_sections_with_openai


def source_from_article(article: dict) -> dict:
    return {"name": article.get("source", "Source"), "url": article.get("url")}


def make_section(title: str, bullets: list[str], sources: list[dict]) -> dict:
    return {"title": title, "bullets": bullets, "sources": sources}


def generate_sections(data: dict) -> dict:
    ranked = data["ranked_articles"]
    top_sources = [source_from_article(article) for article in ranked[:5]]
    sections: dict = {}

    sections["executive_snapshot"] = make_section(
        "Executive Snapshot",
        [
            "Cross-asset focus remains on rates, USD direction, commodity supply signals, and sector leadership.",
            "Portfolio relevance is weighted toward current equity holdings and issuer-level fixed income exposure.",
            "Manual/private pricing issues are retained in audit logs rather than repeated in the newsletter body.",
        ],
        top_sources,
    )

    equity_data = data.get("equity_monitor", {})
    if equity_data:
        sections["portfolio_snapshot"] = {
            "title": "Portfolio Snapshot",
            "kpis": equity_data.get("kpis", []),
            "top_holdings": equity_data.get("top_holdings", []),
            "manual_pricing_count": equity_data.get("manual_pricing_count", 0),
            "invalid_or_manual_holdings": equity_data.get("invalid_or_manual_holdings", []),
        }
        sections["equity_holdings_monitor"] = equity_data

    if data.get("fixed_income_monitor"):
        sections["fixed_income_monitor"] = data["fixed_income_monitor"]

    sections["fx_markets"] = {"title": "FX Markets", "rows": data["fx"]}
    sections["commodities"] = {"title": "Commodities", "rows": data["commodities"]}
    sections["sector_scoreboard"] = {"title": "Sector Scoreboard", "rows": data["sectors"]}

    sections["macro_news"] = make_section(
        "Macro News",
        [item["comment"] for item in data["macro"]],
        [item["source"] for item in data["macro"]],
    )

    sections["private_markets"] = make_section(
        "Private Markets",
        [article["title"] for article in data["private_markets"][:5]],
        [source_from_article(article) for article in data["private_markets"][:5]],
    )

    sections["portfolio_linked_news"] = data.get(
        "portfolio_linked_news",
        {"title": "Portfolio-Linked News", "items": [], "empty_message": "No material portfolio-linked news captured from configured sources this week."},
    )

    sections["regional_headlines"] = data.get("regional_headlines", {"title": "Regional Headlines", "regions": []})

    sections["story_of_the_week"] = select_story_of_the_week(ranked)

    sections["portfolio_watchlist"] = data.get("portfolio_watchlist", {"title": "What to Watch This Week", "rows": []})

    return enhance_sections_with_openai(sections, data)
