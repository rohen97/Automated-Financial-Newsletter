from __future__ import annotations


BANNED_GENERIC_PHRASES = (
    "Near-term underperformance",
    "Leadership broadening",
    "Broad USD momentum",
    "Demand balance",
    "Risk sentiment",
)


def explain_fx(row: dict, macro_rows: list[dict] | None = None, articles: list[dict] | None = None) -> dict:
    label = row.get("label", "FX pair")
    relevance = _fx_relevance(label)
    comment = (
        f"1W: {label} moved {row.get('one_week_change', 0):+.2f}% as rates, USD direction, and regional data shaped short-term positioning. "
        f"1M: the {row.get('one_month_change', 0):+.2f}% move reflects accumulated central-bank repricing and growth differentials. "
        f"YTD: the {row.get('ytd_change', 0):+.2f}% direction remains tied to policy-rate differentials, inflation data, and {relevance}"
    )
    return _result(comment, relevance, 0.62)


def explain_commodity(row: dict, macro_rows: list[dict] | None = None, articles: list[dict] | None = None) -> dict:
    label = row.get("label", "Commodity")
    relevance = _commodity_relevance(label)
    comment = (
        f"1W: {label} moved {row.get('one_week_change', 0):+.2f}% with near-term supply headlines, USD moves, and macro data affecting positioning. "
        f"1M: the {row.get('one_month_change', 0):+.2f}% move reflects inventory, demand expectations, real-yield pressure, and China/global growth signals. "
        f"YTD: the {row.get('ytd_change', 0):+.2f}% direction remains linked to supply restraint, inflation sensitivity, and {relevance}"
    )
    return _result(comment, relevance, 0.60)


def explain_sector(row: dict, region: str, macro_rows: list[dict] | None = None, articles: list[dict] | None = None) -> dict:
    sector = row.get("sector", "Sector")
    relevance = _sector_relevance(region, sector)
    regional_driver = {
        "US": "US rates, earnings expectations, and domestic growth data",
        "Europe": "European growth, ECB expectations, and currency-sensitive earnings",
        "Asia_APAC": "China/APAC growth, regional FX, and policy expectations",
    }.get(region, "regional macro data")
    comment = (
        f"1W: {region} {sector} moved {row.get('one_week', 0):+.2f}% as {regional_driver} affected short-term positioning. "
        f"1M: the {row.get('one_month', 0):+.2f}% move reflects accumulated performance versus regional macro and sector earnings expectations. "
        f"YTD: the {row.get('ytd', 0):+.2f}% direction remains tied to {regional_driver} and {relevance}"
    )
    return _result(comment, relevance, 0.58)


def comments_are_valid(comments: list[str]) -> bool:
    for comment in comments:
        lowered = comment.lower()
        if not all(token in comment for token in ("1W:", "1M:", "YTD:")):
            return False
        if any(phrase.lower() in lowered for phrase in BANNED_GENERIC_PHRASES):
            return False
    return True


def _result(comment: str, relevance: str, confidence: float) -> dict:
    return {
        "comment": comment,
        "driver_1w": _slice(comment, "1W:", "1M:"),
        "driver_1m": _slice(comment, "1M:", "YTD:"),
        "driver_ytd": comment.split("YTD:", 1)[-1].strip(),
        "portfolio_relevance": relevance,
        "supporting_sources": [],
        "confidence_score": confidence,
        "comment_method": "deterministic",
    }


def _slice(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[-1].split(end, 1)[0].strip()


def _fx_relevance(label: str) -> str:
    mapping = {
        "USD/SGD": "Singapore-dollar translation exposure.",
        "AUD/USD": "commodity beta and China/APAC growth sensitivity.",
        "EUR/USD": "European holdings and ECB/Fed rate differentials.",
        "USD/CNH": "China growth and APAC risk transmission.",
        "USD/CNY": "China growth and APAC risk transmission.",
        "USD/JPY": "BoJ/Fed rate differentials and global funding conditions.",
        "DXY": "broad USD translation risk across non-USD holdings.",
    }
    return mapping.get(label, "portfolio currency exposure.")


def _commodity_relevance(label: str) -> str:
    mapping = {
        "Brent": "airline margins, utilities, and inflation sensitivity.",
        "WTI": "inflation sensitivity and energy-sector risk appetite.",
        "Gold": "real yields, USD direction, and defensive hedging demand.",
        "Copper": "China growth and industrial-cycle exposure.",
        "Natural Gas / LNG proxy": "utilities, power prices, and LNG-linked inflation pressure.",
    }
    return mapping.get(label, "inflation and margin sensitivity.")


def _sector_relevance(region: str, sector: str) -> str:
    if region == "Europe" and sector in {"Consumer Discretionary", "Industrials"}:
        return "portfolio relevance for BMW and European cyclicals."
    if region == "Europe" and sector in {"Financials", "Health Care", "Utilities"}:
        return "portfolio relevance for ING, Allianz, Sanofi, and RWE."
    if region == "Asia_APAC" and sector in {"Consumer Discretionary", "Financials", "Industrials"}:
        return "portfolio relevance for Alibaba, Ping An, SATS, and Singapore Airlines."
    if sector in {"Technology", "Real Estate", "Utilities"}:
        return "duration sensitivity across growth, REIT, and utility exposure."
    return "portfolio sector allocation and regional equity beta."
