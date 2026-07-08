from __future__ import annotations

from collections import defaultdict


def group_exposure(holdings: list[dict], key: str) -> list[dict]:
    grouped: dict[str, float] = defaultdict(float)
    for holding in holdings:
        label = holding.get(key) or "Unclassified"
        grouped[label] += float(holding.get("weight", 0))
    return [
        {"name": name, "weight": round(weight, 4)}
        for name, weight in sorted(grouped.items(), key=lambda item: item[1], reverse=True)
    ]


def top_holdings(holdings: list[dict], limit: int = 5) -> list[dict]:
    return sorted(holdings, key=lambda item: float(item.get("weight", 0)), reverse=True)[:limit]


def portfolio_summary(holdings: list[dict]) -> dict:
    total_weight = round(sum(float(item.get("weight", 0)) for item in holdings), 4)
    return {
        "total_weight": total_weight,
        "top_holdings": top_holdings(holdings),
        "asset_class": group_exposure(holdings, "asset_class"),
        "region": group_exposure(holdings, "region"),
        "sector": group_exposure(holdings, "sector"),
        "currency": group_exposure(holdings, "currency"),
    }


def concentration_flags(summary: dict, high_threshold: float = 0.20, medium_threshold: float = 0.10) -> list[str]:
    flags: list[str] = []
    for bucket in ("asset_class", "region", "sector", "currency"):
        for item in summary.get(bucket, []):
            weight = float(item.get("weight", 0))
            if weight >= high_threshold:
                flags.append(f"High {bucket} exposure: {item['name']} at {weight:.0%}.")
            elif weight >= medium_threshold:
                flags.append(f"Material {bucket} exposure: {item['name']} at {weight:.0%}.")
    return flags
