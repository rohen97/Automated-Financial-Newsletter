from __future__ import annotations

import re


REGIONS = ("US", "EU", "UK", "APAC", "EMEA", "Global")

REGION_TERMS = {
    "US": ("united states", "fed", "federal reserve", "treasury", "s&p 500", "nasdaq", "us inflation", "us jobs", "u.s."),
    "EU": ("eurozone", "ecb", "germany", "france", "netherlands", "european", "euro "),
    "UK": ("united kingdom", "boe", "sterling", "gilts", "uk inflation", "britain"),
    "APAC": ("singapore", "china", "hong kong", "india", "japan", "australia", "asean", "mas", "pboc", "asia"),
    "EMEA": ("middle east", "africa", "gulf", "emea", "oil supply", "regional risk"),
    "Global": ("global", "cross-asset", "dollar", "commodities", "geopolitics", "recession"),
}

CATEGORY_TERMS = {
    "Macro": ("macro", "growth", "gdp", "economy", "recession"),
    "Rates": ("rates", "yield", "treasury", "fed", "ecb", "boe", "bond"),
    "FX": ("fx", "currency", "dollar", "usd", "sgd", "euro", "yen", "sterling"),
    "Commodities": ("oil", "brent", "wti", "gold", "copper", "gas", "lng", "commodity"),
    "Equities": ("equity", "stocks", "shares", "earnings", "s&p", "nasdaq"),
    "Credit": ("credit", "spread", "default", "refinancing", "liquidity"),
    "Private Markets": ("private equity", "private credit", "venture", "fundraising", "buyout", "ipo", "exits", "secondaries"),
    "Central Banks": ("central bank", "fed", "ecb", "boe", "mas", "pboc"),
    "Geopolitics": ("geopolitics", "war", "sanctions", "middle east", "tariff"),
}

ASSET_CLASS_TERMS = {
    "Equities": ("equity", "stock", "shares", "earnings", "sector"),
    "Rates": ("yield", "treasury", "bond", "rates", "fed"),
    "FX": ("currency", "usd", "dollar", "fx", "sgd"),
    "Commodities": ("oil", "gold", "copper", "gas", "lng"),
    "Credit": ("credit", "spread", "default", "refinancing"),
    "Private Markets": ("private equity", "private credit", "venture", "buyout"),
}


def enrich_article(article: dict) -> dict:
    enriched = dict(article)
    text = _text(enriched)
    enriched.setdefault("snippet", enriched.get("summary", ""))
    enriched.setdefault("description", enriched.get("summary", ""))
    enriched["region"] = enriched.get("region") or classify_region(text)
    enriched["category"] = _normalise_category(enriched.get("category")) or classify_category(text)
    enriched["asset_class"] = enriched.get("asset_class") or classify_asset_class(text)
    enriched["entities"] = extract_entities(enriched)
    for field in ("matched_holdings", "matched_issuers", "matched_sectors", "matched_currencies"):
        enriched.setdefault(field, [])
    return enriched


def classify_region(text: str) -> str:
    lowered = text.lower()
    for region, terms in REGION_TERMS.items():
        if any(term in lowered for term in terms):
            return region
    return "Global"


def classify_category(text: str) -> str:
    lowered = text.lower()
    for category, terms in CATEGORY_TERMS.items():
        if any(term in lowered for term in terms):
            return category
    return "Macro" if any(term in lowered for term in ("inflation", "jobs", "growth")) else "Equities"


def classify_asset_class(text: str) -> str:
    lowered = text.lower()
    for asset_class, terms in ASSET_CLASS_TERMS.items():
        if any(term in lowered for term in terms):
            return asset_class
    return "Cross-Asset"


def extract_entities(article: dict) -> list[str]:
    title = article.get("title", "")
    words = re.findall(r"\b[A-Z][A-Za-z&.\-]*(?:\s+[A-Z][A-Za-z&.\-]*){0,3}\b", title)
    return [word.strip() for word in words[:8] if len(word.strip()) > 2]


def _normalise_category(category: str | None) -> str | None:
    if not category:
        return None
    mapping = {
        "macro": "Macro",
        "fx": "FX",
        "commodities": "Commodities",
        "private_markets": "Private Markets",
        "markets": "Equities",
        "sectors": "Equities",
    }
    return mapping.get(str(category).lower(), str(category).replace("_", " ").title())


def _text(article: dict) -> str:
    return f"{article.get('title', '')} {article.get('summary', '')} {article.get('description', '')} {article.get('category', '')}"
