from __future__ import annotations

from datetime import UTC, datetime

WEIGHTS = {
    "source_quality": 0.25,
    "portfolio_relevance": 0.25,
    "market_relevance": 0.20,
    "recency": 0.15,
    "regional_balance": 0.10,
    "novelty": 0.05,
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
    haystack = _article_text(article)
    hits = sum(1 for terms in KEYWORDS.values() for term in terms if term in haystack)
    return clamp_score(0.25 + hits * 0.12)


def score_cross_asset_impact(article: dict) -> float:
    haystack = _article_text(article)
    touched = sum(1 for terms in KEYWORDS.values() if any(term in haystack for term in terms))
    return clamp_score(touched / 4)


def score_novelty(article: dict, seen_titles: set[str] | None = None) -> float:
    title = (article.get("title") or "").strip().lower()
    if not title:
        return 0.2
    if seen_titles and title in seen_titles:
        return 0.1
    return 0.8


def score_portfolio_relevance(article: dict) -> float:
    if article.get("matched_holdings"):
        return 1.0
    if article.get("matched_sectors") or article.get("matched_currencies"):
        return 0.7
    haystack = _article_text(article)
    portfolio_terms = ("alibaba", "singapore airlines", "sats", "sembcorp", "allianz", "bmw", "rwe", "sanofi", "capitaLand".lower(), "china", "singapore", "europe", "rates", "oil")
    hits = sum(1 for term in portfolio_terms if term in haystack)
    return clamp_score(0.2 + hits * 0.16)


def score_regional_balance(article: dict, region_counts: dict[str, int] | None = None) -> float:
    if not region_counts:
        return 0.7
    region = article.get("region") or "Global"
    return clamp_score(1.0 - region_counts.get(region, 0) * 0.18)


def _article_text(article: dict) -> str:
    metadata = [
        *article.get("tags", []),
        *article.get("tickers", []),
        *article.get("entities", []),
    ]
    return (
        f"{article.get('title', '')} {article.get('summary', '')} "
        f"{' '.join(str(item) for item in metadata if item)}"
    ).lower()


def importance_score(
    *,
    source_quality: float,
    portfolio_relevance: float = 0.5,
    market_relevance: float,
    novelty: float,
    recency: float,
    regional_balance: float = 0.7,
    cross_asset_impact: float | None = None,
) -> float:
    if cross_asset_impact is not None:
        return round(
            0.30 * clamp_score(source_quality)
            + 0.25 * clamp_score(market_relevance)
            + 0.20 * clamp_score(novelty)
            + 0.15 * clamp_score(cross_asset_impact)
            + 0.10 * clamp_score(recency),
            4,
        )
    return round(
        WEIGHTS["source_quality"] * clamp_score(source_quality)
        + WEIGHTS["portfolio_relevance"] * clamp_score(portfolio_relevance)
        + WEIGHTS["market_relevance"] * clamp_score(market_relevance)
        + WEIGHTS["novelty"] * clamp_score(novelty)
        + WEIGHTS["recency"] * clamp_score(recency)
        + WEIGHTS["regional_balance"] * clamp_score(regional_balance),
        4,
    )


def rank_articles(articles: list[dict], source_quality: dict[str, float] | None = None) -> list[dict]:
    ranked: list[dict] = []
    seen_titles: set[str] = set()
    region_counts: dict[str, int] = {}
    source_quality = source_quality or {}
    for article in articles:
        source = article.get("source") or "Sample Data"
        quality_provider = article.get("source_quality_provider")
        source_quality_score = source_quality.get(
            source,
            source_quality.get(quality_provider, source_quality.get("Sample Data", 0.55)),
        )
        portfolio_relevance_score = score_portfolio_relevance(article)
        market_relevance_score = score_market_relevance(article)
        recency_score = score_recency(article.get("published_at"))
        regional_balance_score = score_regional_balance(article, region_counts)
        novelty_score = score_novelty(article, seen_titles)
        score = importance_score(
            source_quality=source_quality_score,
            portfolio_relevance=portfolio_relevance_score,
            market_relevance=market_relevance_score,
            novelty=novelty_score,
            recency=recency_score,
            regional_balance=regional_balance_score,
        )
        enriched = {
            **article,
            "source_quality_score": round(source_quality_score, 4),
            "portfolio_relevance_score": round(portfolio_relevance_score, 4),
            "market_relevance_score": round(market_relevance_score, 4),
            "recency_score": round(recency_score, 4),
            "regional_balance_score": round(regional_balance_score, 4),
            "novelty_score": round(novelty_score, 4),
            "importance_score": score,
        }
        ranked.append(enriched)
        region = article.get("region") or "Global"
        region_counts[region] = region_counts.get(region, 0) + 1
        if article.get("title"):
            seen_titles.add(article["title"].strip().lower())
    return sorted(ranked, key=lambda item: item["importance_score"], reverse=True)
