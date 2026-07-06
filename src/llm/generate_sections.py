from __future__ import annotations

from src.analysis.calendar_watchlist import build_watchlist
from src.analysis.market_moves import summarize_market_table
from src.analysis.story_selector import select_story_of_the_week


def source_from_article(article: dict) -> dict:
    return {"name": article.get("source", "Source"), "url": article.get("url")}


def source_from_row(row: dict) -> dict:
    return row.get("source") or {"name": "Sample Data", "url": "https://example.com/wolf-research/sample-data"}


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
            "The content engine ranks stories by source quality, market relevance, novelty, cross-asset impact, and recency.",
            "All outputs are analytical context for internal distribution, not investment recommendations.",
        ],
        top_sources,
    )
    sections["macro_news"] = make_section(
        "Macro News",
        [item["comment"] for item in data["macro"]],
        [item["source"] for item in data["macro"]],
    )
    sections["fx_markets"] = {"title": "FX Markets", "rows": data["fx"]}
    sections["commodities"] = {"title": "Commodities", "rows": data["commodities"]}
    sections["private_markets"] = make_section(
        "Private Markets",
        [article["title"] for article in data["private_markets"][:5]],
        [source_from_article(article) for article in data["private_markets"][:5]],
    )
    sections["sector_scoreboard"] = make_section(
        "Sector Scoreboard",
        summarize_market_table(data["sectors"], name_key="sector"),
        [source_from_row(row) for row in data["sectors"][:5]],
    )
    sections["story_of_the_week"] = select_story_of_the_week(ranked)
    sections["week_in_headlines"] = [
        {
            "title": article["title"],
            "source": source_from_article(article),
            "category": article.get("category", "markets"),
            "importance_score": article.get("importance_score", 0),
        }
        for article in ranked[:10]
    ]
    sections["watchlist"] = build_watchlist(ranked)
    return sections
