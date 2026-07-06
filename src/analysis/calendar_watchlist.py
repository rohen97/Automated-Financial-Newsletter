from __future__ import annotations


def build_watchlist(articles: list[dict]) -> list[dict]:
    items = [
        {
            "event": "Inflation and central bank communication",
            "why_it_matters": "Rates expectations remain the main cross-asset transmission channel.",
            "source": {"name": "Sample Data", "url": "https://example.com/wolf-research/watchlist/inflation"},
        },
        {
            "event": "USD and Asian FX momentum",
            "why_it_matters": "Currency volatility affects Singapore-based portfolio translation risk.",
            "source": {"name": "Sample Data", "url": "https://example.com/wolf-research/watchlist/fx"},
        },
    ]
    if articles:
        items.append(
            {
                "event": articles[0]["title"],
                "why_it_matters": "Highest-ranked current headline in the content engine.",
                "source": {"name": articles[0].get("source", "Source"), "url": articles[0].get("url")},
            }
        )
    return items
