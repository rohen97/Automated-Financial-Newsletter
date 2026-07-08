from __future__ import annotations

REGIONS = ("US", "EU", "UK", "APAC", "EMEA", "Global")


THEME_MAP = {
    "alibaba": ("APAC", "China growth", "Consumer and internet risk"),
    "bmw": ("EU", "Autos", "European growth and rates"),
    "allianz": ("EU", "Insurance", "Rates and credit spreads"),
    "singapore airlines": ("APAC", "Travel", "Oil and regional demand"),
    "sembcorp": ("APAC", "Utilities / energy transition", "Power prices and gas markets"),
    "rwe": ("EU", "Utilities / energy transition", "Power prices and policy"),
    "microsoft": ("US", "US tech / AI", "Rates duration and AI capex"),
    "alphabet": ("US", "US tech / AI", "Rates duration and digital advertising"),
    "amazon": ("US", "US tech / AI", "Rates duration and cloud demand"),
    "apple": ("US", "US tech / hardware", "Consumer demand and supply chains"),
    "kfw": ("EU", "Supranational / rates", "Credit spreads and European rates"),
    "european investment bank": ("EU", "Supranational / rates", "Credit spreads and European rates"),
    "asian development bank": ("APAC", "Supranational / rates", "APAC credit spreads"),
    "international bank for reconstruction": ("Global", "Supranational / rates", "Global credit spreads"),
}


def infer_region(article: dict) -> str:
    if article.get("region") in REGIONS:
        return article["region"]
    text = f"{article.get('title', '')} {article.get('summary', '')} {article.get('category', '')}".lower()
    if any(term in text for term in ("fed", "usd", "nasdaq", "s&p", "us ", "u.s.")):
        return "US"
    if any(term in text for term in ("ecb", "euro", "europe", "germany", "france")):
        return "EU"
    if "uk" in text or "boe" in text or "britain" in text:
        return "UK"
    if any(term in text for term in ("china", "singapore", "apac", "asia", "sgd", "hkd")):
        return "APAC"
    if any(term in text for term in ("emea", "middle east", "africa")):
        return "EMEA"
    return "Global"


def regional_headlines(articles: list[dict]) -> dict:
    grouped = {region: [] for region in REGIONS}
    for article in articles:
        region = infer_region(article)
        if len(grouped[region]) < 3:
            grouped[region].append(
                {
                    "headline": article.get("title", ""),
                    "source": "Fallback source" if article.get("source") == "Sample Data" else article.get("source", "Source"),
                    "category": article.get("category", "markets"),
                    "url": article.get("url", ""),
                }
            )
    return {"title": "Regional Headlines", "regions": [{"region": region, "headlines": grouped[region]} for region in REGIONS]}


def _issuer_name(item: str | dict) -> str:
    return item if isinstance(item, str) else item.get("issuer", "")


def portfolio_linked_news(equity_holdings: list[dict], issuers: list[str | dict], articles: list[dict]) -> dict:
    linked = []
    names = [(item.get("holding", ""), "Equity", item.get("currency", ""), item.get("sector", "")) for item in equity_holdings]
    seen_issuers = set()
    for issuer_item in issuers:
        issuer = _issuer_name(issuer_item)
        if issuer and issuer not in seen_issuers:
            names.append((issuer, "Fixed Income", "", ""))
            seen_issuers.add(issuer)
    for name, asset_class, currency, sector in names:
        key = name.lower()
        matched_theme = None
        for theme_key, mapping in THEME_MAP.items():
            if theme_key in key:
                matched_theme = mapping
                break
        for article in articles:
            text = f"{article.get('title', '')} {article.get('summary', '')}".lower()
            if key and key in text:
                region, theme, why = matched_theme or (infer_region(article), sector or currency or "Portfolio exposure", "Potential exposure-specific relevance")
                linked.append(
                    {
                        "name": name,
                        "region": region,
                        "asset_class": asset_class,
                        "news_theme": theme,
                        "why_it_matters": why,
                        "source": {
                            "name": "Fallback source" if article.get("source") == "Sample Data" else article.get("source", "Source"),
                            "url": article.get("url", ""),
                        },
                    }
                )
                break
    return {
        "title": "Portfolio-Linked News",
        "items": linked[:10],
        "empty_message": "No material portfolio-linked news captured from configured sources this week.",
    }


def portfolio_watchlist() -> dict:
    return {
        "title": "What to Watch This Week",
        "rows": [
            {"period": "This week", "region": "US", "event": "Inflation and Fed communication", "portfolio_relevance": "Impacts USD, duration, and US growth holdings", "asset_classes": "FX, rates, equities"},
            {"period": "This week", "region": "EU", "event": "ECB / European growth data", "portfolio_relevance": "Relevant for Allianz, BMW, RWE, Sanofi, Roche, KFW, EIB", "asset_classes": "Equities, credit"},
            {"period": "This week", "region": "APAC", "event": "China activity and Singapore macro", "portfolio_relevance": "Relevant for Alibaba, SATS, SIA, Sembcorp, SGD exposure", "asset_classes": "Equities, FX"},
            {"period": "This week", "region": "Global", "event": "Oil and LNG supply headlines", "portfolio_relevance": "Relevant for inflation, airlines, utilities, and commodities", "asset_classes": "Commodities, rates"},
            {"period": "This week", "region": "EMEA", "event": "Credit spread and geopolitical risk", "portfolio_relevance": "Relevant for bond issuer risk and risk sentiment", "asset_classes": "Credit, FX"},
        ],
    }
