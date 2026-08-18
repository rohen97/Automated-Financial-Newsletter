from __future__ import annotations


def _terms(values: list[str]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        if value:
            terms.add(value.lower())
            terms.update(part.lower() for part in value.replace("/", " ").split())
    return terms


def portfolio_terms(holdings: list[dict]) -> set[str]:
    values: list[str] = []
    for holding in holdings:
        values.extend(
            [
                holding.get("holding", ""),
                holding.get("asset_class", ""),
                holding.get("region", ""),
                holding.get("sector", ""),
                holding.get("currency", ""),
            ]
        )
    return _terms(values)


def portfolio_relevance_score(article: dict, holdings: list[dict]) -> float:
    if not holdings:
        return 0.0
    terms = portfolio_terms(holdings)
    metadata = [
        *article.get("tags", []),
        *article.get("tickers", []),
        *article.get("entities", []),
    ]
    haystack = (
        f"{article.get('title', '')} {article.get('summary', '')} "
        f"{article.get('category', '')} {' '.join(str(item) for item in metadata if item)}"
    ).lower()
    hits = sum(1 for term in terms if len(term) > 2 and term in haystack)
    return min(1.0, round(hits / 6, 4))


def enrich_articles_with_portfolio_relevance(articles: list[dict], holdings: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for article in articles:
        relevance = portfolio_relevance_score(article, holdings)
        blended_score = round((float(article.get("importance_score", 0)) * 0.75) + (relevance * 0.25), 4)
        enriched.append(
            {
                **article,
                "portfolio_relevance": relevance,
                "portfolio_adjusted_score": blended_score,
            }
        )
    return sorted(enriched, key=lambda item: item["portfolio_adjusted_score"], reverse=True)
