from __future__ import annotations


def select_story_of_the_week(articles: list[dict]) -> dict:
    if not articles:
        return {
            "title": "No dominant story identified",
            "narrative": "Insufficient source material was available.",
            "implications": [],
            "sources": [],
        }
    top = articles[0]
    return {
        "title": top["title"],
        "narrative": top.get("summary") or top["title"],
        "implications": [
            "Monitor whether the theme affects rates, FX, commodities, and sector leadership.",
            "Treat this as analytical context, not an investment recommendation.",
        ],
        "sources": [{"name": top.get("source", "Source"), "url": top.get("url")}],
    }
