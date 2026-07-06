from __future__ import annotations

from datetime import UTC, datetime

WEIGHTS = {
    "source_quality": 0.30,
    "market_relevance": 0.25,
    "novelty": 0.20,
    "cross_asset_impact": 0.15,
    "recency": 0.10,
}

KEYWORDS = {
    "macro": ("inflation", "central bank", "fed", "rates", "growth", "gdp", "jobs"),
    "fx": ("currency", "dollar", "usd", "sgd", "aud", "eur", "yen", "fx"),
    "commodities": ("oil", "brent", "wti", "gold", "copper", "gas", "lng"),
    "private_markets": ("private equity", "venture", "buyout", "fundraising", "ipo"),
    "sectors": ("sector", "earnings", "semiconductor", "banks", "energy", "healthcare"),
}


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_recency(published_at: datetime | None, now: datetime | None = None) -> float:
    if published_at is None:
        return 0.4
    now = now or datetime.now(UTC)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    age_hours = max((now - published_at).total_seconds() / 3600, 0)
    return clamp_score(1 - (age_hours / (7 * 24)))


def score_market_relevance(article: dict) -> float:
    haystack = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    hits = sum(1 for terms in KEYWORDS.values() for term in terms if term in haystack)
    return clamp_score(0.25 + hits * 0.12)


def score_cross_asset_impact(article: dict) -> float:
    haystack = f"{article.get('title', '')} {article.get('summary', '')}".lower()
    touched = sum(1 for terms in KEYWORDS.values() if any(term in haystack for term in terms))
    return clamp_score(touched / 4)


def score_novelty(article: dict, seen_titles: set[str] | None = None) -> float:
    title = (article.get("title") or "").strip().lower()
    if not title:
        return 0.2
    if seen_titles and title in seen_titles:
        return 0.1
    return 0.8


def importance_score(
    *,
    source_quality: float,
    market_relevance: float,
    novelty: float,
    cross_asset_impact: float,
    recency: float,
) -> float:
    return round(
        WEIGHTS["source_quality"] * clamp_score(source_quality)
        + WEIGHTS["market_relevance"] * clamp_score(market_relevance)
        + WEIGHTS["novelty"] * clamp_score(novelty)
        + WEIGHTS["cross_asset_impact"] * clamp_score(cross_asset_impact)
        + WEIGHTS["recency"] * clamp_score(recency),
        4,
    )


def rank_articles(articles: list[dict], source_quality: dict[str, float] | None = None) -> list[dict]:
    ranked: list[dict] = []
    seen_titles: set[str] = set()
    source_quality = source_quality or {}
    for article in articles:
        source = article.get("source") or "Sample Data"
        score = importance_score(
            source_quality=source_quality.get(source, source_quality.get("Sample Data", 0.55)),
            market_relevance=score_market_relevance(article),
            novelty=score_novelty(article, seen_titles),
            cross_asset_impact=score_cross_asset_impact(article),
            recency=score_recency(article.get("published_at")),
        )
        enriched = {**article, "importance_score": score}
        ranked.append(enriched)
        if article.get("title"):
            seen_titles.add(article["title"].strip().lower())
    return sorted(ranked, key=lambda item: item["importance_score"], reverse=True)
