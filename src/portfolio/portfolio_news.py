from __future__ import annotations

from src.processing.article_enrichment import REGIONS, classify_category, classify_region


ALIASES = {
    "Meta Wolf AG": ["meta wolf", "meta wolf ag", "european building materials", "german capital goods"],
    "ING Groep NV": ["ing", "ing groep", "dutch banks", "european banks"],
    "SATS Ltd": ["sats", "singapore aviation services", "ground handling"],
    "Singapore Airlines Ltd": ["singapore airlines", "sia", "airlines", "aviation", "travel demand", "jet fuel"],
    "Sembcorp Industries Ltd": ["sembcorp", "singapore utilities", "energy transition", "power"],
    "Allianz SE": ["allianz", "european insurance", "insurers"],
    "RWE AG": ["rwe", "european utilities", "renewable power", "power prices"],
    "CapitaLand Ascendas REIT": ["capitaland ascendas", "ascendas reit", "singapore reits", "industrial reits"],
    "Ping An Insurance Group Co": ["ping an", "chinese insurance", "china financials"],
    "Sanofi SA": ["sanofi", "pharma", "european healthcare"],
    "CapitaLand Investment Ltd/Sing": ["capitaland investment", "singapore real estate", "asset management"],
    "Alibaba Group Holding Ltd": ["alibaba", "china internet", "chinese ecommerce", "china tech"],
    "Bayerische Motoren Werke AG": ["bmw", "bayerische motoren werke", "european autos", "german autos"],
    "Softtech Engineers Ltd": ["softtech engineers", "indian software", "india technology"],
}

SECTOR_THEME = {
    "technology": ("Technology duration / AI / software", "Rates and growth expectations affect technology valuation multiples."),
    "industrials": ("Transport and industrial cycle", "Oil, travel demand, and regional growth affect transport and industrial exposure."),
    "utilities": ("Utilities and power prices", "Rates, power prices, and energy-transition policy affect utility cash-flow expectations."),
    "insurance": ("Insurance and rates", "Rates and credit spreads affect insurer reinvestment income and capital-market sensitivity."),
    "financials": ("Financials and credit", "Rates, curve shape, and credit conditions affect financial-sector risk."),
    "health care": ("Healthcare defensiveness", "Policy, rates, and European growth affect healthcare defensiveness and valuation."),
    "real estate": ("Real estate and rates", "Long-end yields affect REIT valuations and funding costs."),
}

REGION_RELEVANCE = {
    "EU": ("European growth and rates", "Relevant for Allianz, BMW, RWE, Sanofi, ING, and Meta Wolf AG."),
    "APAC": ("APAC growth and currency risk", "Relevant for Alibaba, SATS, SIA, Sembcorp, CapitaLand, Ping An, and SGD/CNY exposure."),
    "US": ("US rates and global risk appetite", "Relevant for equity duration, USD direction, and global funding conditions."),
    "Global": ("Global cross-asset risk", "Relevant for portfolio beta, commodities, FX, and funding conditions."),
    "EMEA": ("EMEA geopolitical and commodity risk", "Relevant for oil, LNG, inflation, airlines, and risk sentiment."),
    "UK": ("UK rates and sterling risk", "Relevant as a developed-market rates and currency signal."),
}


def infer_region(article: dict) -> str:
    if article.get("region") in REGIONS:
        return article["region"]
    return classify_region(f"{article.get('title', '')} {article.get('summary', '')} {article.get('category', '')}")


def regional_headlines(articles: list[dict], max_per_region: int = 3) -> dict:
    grouped = {region: [] for region in REGIONS}
    for article in articles:
        if not article.get("url"):
            continue
        if not _is_real_source_article(article):
            continue
        region = infer_region(article)
        if len(grouped[region]) < max_per_region:
            grouped[region].append(
                {
                    "headline": article.get("title", ""),
                    "source": _source_name(article),
                    "category": article.get("category") or classify_category(f"{article.get('title', '')} {article.get('summary', '')}"),
                    "url": article.get("url", ""),
                    "market_implication": _market_implication(article),
                }
            )
    return {"title": "Regional Headlines", "regions": [{"region": region, "headlines": grouped[region]} for region in REGIONS]}


def portfolio_linked_news(equity_holdings: list[dict], issuers: list[str | dict], articles: list[dict]) -> dict:
    linked = []
    seen_urls = set()
    holdings = _holding_profiles(equity_holdings)
    url_articles = [article for article in articles if _is_real_source_article(article)]

    for profile in holdings:
        direct = _best_direct_match(profile, url_articles, seen_urls)
        if direct:
            linked.append(direct)
            seen_urls.add(direct["source"]["url"])
        if len(linked) >= 8:
            break

    if len(linked) < 8:
        for article in url_articles:
            if article.get("url") in seen_urls:
                continue
            fallback = _sector_region_match(article, holdings)
            if fallback:
                linked.append(fallback)
                seen_urls.add(article["url"])
            if len(linked) >= 8:
                break

    return {
        "title": "Portfolio-Linked News",
        "items": linked[:8],
        "empty_message": "No material portfolio-linked news captured from configured sources this week.",
    }


def portfolio_watchlist() -> dict:
    return {
        "title": "What to Watch This Week",
        "rows": [
            {"period": "This week", "region": "US", "event": "Inflation and Fed communication", "portfolio_relevance": "Impacts USD, duration, and growth-style equity valuation", "asset_classes": "FX, rates, equities"},
            {"period": "This week", "region": "EU", "event": "ECB / European growth data", "portfolio_relevance": "Relevant for Allianz, BMW, RWE, Sanofi, ING, and Meta Wolf AG", "asset_classes": "Equities, credit"},
            {"period": "This week", "region": "APAC", "event": "China activity and Singapore macro", "portfolio_relevance": "Relevant for Alibaba, SATS, SIA, Sembcorp, CapitaLand, Ping An, and SGD exposure", "asset_classes": "Equities, FX"},
            {"period": "This week", "region": "Global", "event": "Oil and LNG supply headlines", "portfolio_relevance": "Relevant for inflation, airlines, utilities, and commodities exposure", "asset_classes": "Commodities, rates"},
            {"period": "This week", "region": "EMEA", "event": "Credit spread and geopolitical risk", "portfolio_relevance": "Relevant for risk sentiment, oil prices, and funding conditions", "asset_classes": "Credit, FX"},
        ],
    }


def _holding_profiles(equity_holdings: list[dict]) -> list[dict]:
    profiles = []
    for holding in equity_holdings:
        name = holding.get("holding", "")
        aliases = ALIASES.get(name, [name.lower()])
        profiles.append(
            {
                "name": name,
                "aliases": [alias.lower() for alias in aliases + [name]],
                "sector": str(holding.get("sector", "")).lower(),
                "currency": str(holding.get("currency", "")).upper(),
                "region": _holding_region(holding),
            }
        )
    return profiles


def _best_direct_match(profile: dict, articles: list[dict], seen_urls: set[str]) -> dict | None:
    for article in articles:
        if article.get("url") in seen_urls:
            continue
        text = _article_text(article)
        if any(alias and alias in text for alias in profile["aliases"]):
            return _linked_item(profile["name"], profile["region"], "Equity", _theme_for_profile(profile), _why_for_profile(profile), article)
    return None


def _sector_region_match(article: dict, holdings: list[dict]) -> dict | None:
    text = _article_text(article)
    region = infer_region(article)
    for profile in holdings:
        if profile["sector"] and profile["sector"] in text:
            theme, why = SECTOR_THEME.get(profile["sector"], (f"{profile['sector'].title()} exposure", "Sector news may affect portfolio exposure."))
            return _linked_item(profile["name"], profile["region"], "Equity", theme, why, article)
    if region in REGION_RELEVANCE:
        theme, why = REGION_RELEVANCE[region]
        return _linked_item(f"{region} portfolio exposure", region, "Equity / Macro", theme, why, article)
    return None


def _linked_item(name: str, region: str, asset_class: str, theme: str, why: str, article: dict) -> dict:
    return {
        "name": name,
        "region": region,
        "asset_class": asset_class,
        "news_theme": theme,
        "why_it_matters": why,
        "source": {"name": _source_name(article), "url": article.get("url", "")},
    }


def _theme_for_profile(profile: dict) -> str:
    theme, _ = SECTOR_THEME.get(profile["sector"], (profile["sector"].title() or "Portfolio exposure", ""))
    return theme


def _why_for_profile(profile: dict) -> str:
    _, why = SECTOR_THEME.get(profile["sector"], ("", "Potential exposure-specific relevance for the equity portfolio."))
    return why


def _holding_region(holding: dict) -> str:
    currency = str(holding.get("currency", "")).upper()
    if currency in {"SGD", "HKD", "CNY", "INR"}:
        return "APAC"
    if currency in {"EUR", "CHF"}:
        return "EU"
    if currency == "GBP":
        return "UK"
    if currency == "USD":
        return "US"
    return "Global"


def _market_implication(article: dict) -> str:
    category = str(article.get("category", "")).lower()
    if "rates" in category or "central" in category:
        return "Rates path can affect discount rates, FX, and equity multiples."
    if "commod" in category:
        return "Commodity moves can affect inflation, airlines, utilities, and margins."
    if "credit" in category or "private" in category:
        return "Credit conditions can affect funding windows and private-market exits."
    if "fx" in category:
        return "Currency moves affect translation risk and regional competitiveness."
    return "Monitor for cross-asset risk appetite and portfolio relevance."


def _source_name(article: dict) -> str:
    return "Source" if article.get("source") == "Sample Data" else article.get("source", "Source")


def _article_text(article: dict) -> str:
    metadata = [
        *article.get("tags", []),
        *article.get("tickers", []),
        *article.get("entities", []),
    ]
    return (
        f"{article.get('title', '')} {article.get('summary', '')} "
        f"{article.get('description', '')} {article.get('category', '')} "
        f"{' '.join(str(item) for item in metadata if item)}"
    ).lower()


def _is_real_source_article(article: dict) -> bool:
    url = str(article.get("url", ""))
    return bool(url) and "example.com/wolf-research" not in url and article.get("source") != "Sample Data"
