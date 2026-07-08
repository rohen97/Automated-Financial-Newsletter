from __future__ import annotations

from datetime import UTC, datetime, timedelta


def sample_series(label: str, base: float) -> dict:
    return {
        "label": label,
        "last": round(base, 4),
        "one_week_change": round(base * 0.004, 4),
        "one_month_change": round(base * 0.013, 4),
        "driver": "Fallback sample data. Replace with configured market data API in production.",
        "source": {"name": "Sample Data", "url": "https://example.com/wolf-research/sample-data"},
    }


def sample_article(title: str, category: str, source: str = "Sample Data", days_ago: int = 1) -> dict:
    published = datetime.now(UTC) - timedelta(days=days_ago)
    slug = title.lower().replace(" ", "-").replace("/", "-")
    return {
        "title": title,
        "source": source,
        "published_at": published,
        "date": published.date().isoformat(),
        "url": f"https://example.com/wolf-research/{category}/{slug}",
        "summary": f"{title}. Focus remains on portfolio implications, risk transmission, and cross-asset context.",
        "category": category,
    }
