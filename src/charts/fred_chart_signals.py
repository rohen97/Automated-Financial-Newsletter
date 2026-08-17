from __future__ import annotations


KEYWORDS = {
    "us_10y_yield": ["rates", "fed", "treasury", "yield", "yields", "duration"],
    "yield_curve": ["recession", "curve", "slowdown", "steepening", "inversion"],
    "high_yield_spreads": ["credit", "spreads", "default", "refinancing", "private credit"],
    "financial_stress": ["stress", "volatility", "banking", "liquidity", "risk-off"],
    "inflation_path": ["inflation", "cpi", "prices", "disinflation"],
    "labour_market": ["jobs", "payrolls", "unemployment", "labour", "labor", "wages"],
    "real_rates": ["real yields", "real rates", "gold", "tips"],
    "policy_vs_inflation": ["fed funds", "policy", "restrictive", "rate cut", "rate-cut", "inflation"],
}

PORTFOLIO_KEYWORDS = {
    "us_10y_yield": ["technology", "reit", "utilities", "growth"],
    "yield_curve": ["financials", "industrials", "cyclicals"],
    "high_yield_spreads": ["private", "credit", "financials"],
    "financial_stress": ["financials", "insurance", "banks"],
    "inflation_path": ["airlines", "transport", "utilities", "consumer"],
    "labour_market": ["consumer", "industrials", "travel"],
    "real_rates": ["technology", "reit", "gold", "utilities"],
    "policy_vs_inflation": ["technology", "financials", "reit", "fx"],
}


def market_move_score(rows_by_series: dict[str, list[dict]]) -> float:
    scores = []
    for rows in rows_by_series.values():
        if len(rows) < 5:
            continue
        values = [row["value"] for row in rows]
        one_week = values[-1] - values[max(0, len(values) - 6)]
        one_month = values[-1] - values[max(0, len(values) - 22)]
        three_month = values[-1] - values[max(0, len(values) - 66)]
        changes = [values[idx] - values[idx - 1] for idx in range(1, len(values))]
        sample = changes[-252:] if len(changes) > 252 else changes
        mean = sum(sample) / len(sample)
        variance = sum((value - mean) ** 2 for value in sample) / len(sample)
        std = variance**0.5 or 1.0
        z = max(abs(one_week), abs(one_month) / 4, abs(three_month) / 13) / std
        scores.append(min(1.0, z / 2.5))
    return max(scores) if scores else 0.0


def news_relevance_score(chart_id: str, articles: list[dict]) -> float:
    if not articles:
        return 0.0
    terms = KEYWORDS.get(chart_id, [])
    hits = 0
    for article in articles[:40]:
        text = f"{article.get('title', '')} {article.get('summary', '')} {article.get('category', '')}".lower()
        if any(term in text for term in terms):
            hits += 1
    return min(1.0, hits / 4)


def portfolio_relevance_score(chart_id: str, equity_monitor: dict | None = None) -> float:
    if not equity_monitor:
        return 0.45 if chart_id in {"us_10y_yield", "policy_vs_inflation"} else 0.25
    text_parts = []
    for row in equity_monitor.get("sector_exposure", []):
        text_parts.append(str(row.get("name", "")))
    for row in equity_monitor.get("top_holdings", []):
        text_parts.append(str(row.get("holding", "")))
        text_parts.append(str(row.get("sector", "")))
    text = " ".join(text_parts).lower()
    hits = sum(1 for term in PORTFOLIO_KEYWORDS.get(chart_id, []) if term in text)
    base = 0.35 if chart_id in {"us_10y_yield", "policy_vs_inflation", "real_rates"} else 0.2
    return min(1.0, base + hits * 0.18)


def regime_relevance_score(chart_id: str, articles: list[dict], rows_by_series: dict[str, list[dict]]) -> float:
    text = " ".join(f"{a.get('title', '')} {a.get('summary', '')}" for a in articles[:30]).lower()
    if any(term in text for term in ["fed", "treasury", "yield", "rate cut", "rates"]):
        return 0.85 if chart_id in {"us_10y_yield", "real_rates", "policy_vs_inflation"} else 0.35
    if any(term in text for term in ["inflation", "cpi", "prices"]):
        return 0.85 if chart_id in {"inflation_path", "policy_vs_inflation"} else 0.3
    if any(term in text for term in ["credit", "spread", "default", "liquidity"]):
        return 0.85 if chart_id in {"high_yield_spreads", "financial_stress"} else 0.3
    if any(term in text for term in ["jobs", "payrolls", "unemployment"]):
        return 0.85 if chart_id == "labour_market" else 0.3
    if market_move_score(rows_by_series) > 0.65:
        return 0.65
    return 0.4


def freshness_score(chart_id: str, history: list[dict], avoid_weeks: int) -> float:
    recent = [item.get("chart_id") for item in history[-avoid_weeks:]]
    return 0.15 if chart_id in recent else 1.0


def trigger_boost(chart_id: str, rows_by_series: dict[str, list[dict]]) -> tuple[float, str]:
    score = market_move_score(rows_by_series)
    if score < 0.55:
        return 0.0, "No large data trigger detected."
    reasons = {
        "us_10y_yield": "US 10Y yield moved meaningfully over recent windows.",
        "yield_curve": "Yield curve moved meaningfully over recent windows.",
        "high_yield_spreads": "High-yield spreads moved meaningfully over recent windows.",
        "financial_stress": "Financial stress moved meaningfully over recent windows.",
        "inflation_path": "Inflation data moved meaningfully over recent windows.",
        "labour_market": "Labour-market data moved meaningfully over recent windows.",
        "real_rates": "Real yields moved meaningfully over recent windows.",
        "policy_vs_inflation": "Policy/inflation relationship moved meaningfully over recent windows.",
    }
    return min(0.15, score * 0.15), reasons.get(chart_id, "Data trigger detected.")
