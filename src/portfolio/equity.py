from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.utils.io import project_path

MANUAL_LABEL = "Manual pricing required"
MISSING_LABEL = "--"
INVALID_MARKERS = {"", "#N/A", "#N/A Invalid", "N/A", "NA", "nan", "None", "null", None}

COLUMN_ALIASES = {
    "stock_name": {"stock_name", "stock name", "holding", "name", "company"},
    "ticker": {"ticker", "symbol"},
    "currency": {"currency", "ccy"},
    "average_cost_price": {"average_cost_price", "average cost price / share", "average cost price", "avg cost", "average cost"},
    "current_price": {"current_price", "current price / share", "current price", "last price"},
    "ytd_share_price_performance_pct": {
        "ytd_share_price_performance_pct",
        "ytd share price performance (%)",
        "ytd share price performance",
    },
    "shares_bought": {"shares_bought", "# of shares bought", "shares bought", "shares", "quantity"},
    "market_cap_usd_millions": {"market_cap_usd_millions", "market cap (usd millions)", "market cap usd millions"},
    "current_investment_value_usd": {
        "current_investment_value_usd",
        "current investment value (usd)",
        "current investment value",
        "current_value",
    },
    "ytd_performance_usd": {"ytd_performance_usd", "ytd performance (usd)", "ytd performance", "ytd_pnl"},
    "ytd_performance_pct": {"ytd_performance_pct", "ytd performance (%)", "ytd_pct"},
    "industry_sector": {"industry_sector", "industry sector", "sector"},
    "region": {"region"},
    "country": {"country"},
    "pricing_mode": {"pricing_mode", "pricing mode", "pricing_status", "pricing status"},
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def clean_column_name(value: Any) -> str:
    text = _clean(value).lower()
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _canonical_key(raw_key: str) -> str:
    cleaned = clean_column_name(raw_key)
    for canonical, aliases in COLUMN_ALIASES.items():
        if cleaned in {clean_column_name(alias) for alias in aliases}:
            return canonical
    return cleaned.replace(" ", "_")


def _is_invalid(value: Any) -> bool:
    text = _clean(value)
    return text in INVALID_MARKERS


def parse_number(value: Any) -> float | None:
    if _is_invalid(value):
        return None
    text = _clean(value)
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    text = text.replace(",", "").replace("%", "")
    text = re.sub(r"(?i)\busd\b|\bsgd\b|\beur\b|\bhkd\b|\binr\b", "", text)
    text = text.replace("$", "").strip()
    if text.startswith("-"):
        negative = True
        text = text[1:].strip()
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def parse_money(value: Any) -> float | None:
    return parse_number(value)


def parse_percent(value: Any) -> float | None:
    return parse_number(value)


def _format_usd(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return MANUAL_LABEL
    sign = ""
    if signed:
        sign = "+" if value > 0 else "-" if value < 0 else ""
    amount = abs(value)
    if amount >= 1_000_000:
        return f"{sign}USD {amount / 1_000_000:.1f}m"
    if amount >= 1_000:
        return f"{sign}USD {amount / 1_000:.1f}k"
    return f"{sign}USD {amount:,.0f}"


def _format_percent(value: float | None) -> str:
    if value is None:
        return MANUAL_LABEL
    return f"{value:+.2f}%"


def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for key, value in row.items():
        canonical[_canonical_key(key)] = value
    return canonical


def load_equity_holdings(path: str | Path = "data/portfolio/equity_holdings.csv") -> list[dict]:
    target = Path(path)
    if not target.is_absolute():
        target = project_path(str(target))
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    holdings = []
    for raw_row in rows:
        row = _normalise_row(raw_row)
        current_value = parse_money(row.get("current_investment_value_usd"))
        ytd_pnl = parse_money(row.get("ytd_performance_usd"))
        ytd_pct = parse_percent(row.get("ytd_performance_pct"))
        missing_pricing = current_value is None and ytd_pnl is None and ytd_pct is None
        pricing_mode = (_clean(row.get("pricing_mode")) or "manual").lower()
        holding = {
            "holding": _clean(row.get("stock_name")),
            "stock_name": _clean(row.get("stock_name")),
            "ticker": _clean(row.get("ticker")),
            "currency": _clean(row.get("currency")),
            "sector": _clean(row.get("industry_sector")) or "Unclassified",
            "industry_sector": _clean(row.get("industry_sector")) or "Unclassified",
            "region": _clean(row.get("region")) or "Unknown",
            "country": _clean(row.get("country")) or "Unknown",
            "average_cost_price": parse_number(row.get("average_cost_price")),
            "current_price": parse_number(row.get("current_price")),
            "ytd_share_price_performance_pct": parse_percent(row.get("ytd_share_price_performance_pct")),
            "shares_bought": parse_number(row.get("shares_bought")),
            "market_cap_usd_millions": parse_number(row.get("market_cap_usd_millions")),
            "current_value": current_value,
            "current_investment_value_usd": current_value,
            "ytd_pnl": ytd_pnl,
            "ytd_performance_usd": ytd_pnl,
            "ytd_pct": ytd_pct,
            "ytd_performance_pct": ytd_pct,
            "pricing_status": pricing_mode,
            "pricing_mode": pricing_mode,
            "is_manual_pricing": missing_pricing,
            "has_usable_pricing": not missing_pricing,
        }
        holding["current_value_display"] = _format_usd(current_value)
        holding["ytd_pnl_display"] = _format_usd(ytd_pnl, signed=True)
        holding["ytd_pct_display"] = _format_percent(ytd_pct)
        holdings.append(holding)
    return holdings


def _numeric_holdings(holdings: list[dict], key: str) -> list[dict]:
    return [holding for holding in holdings if holding.get(key) is not None]


def top_by_value(holdings: list[dict], limit: int = 8) -> list[dict]:
    numeric = _numeric_holdings(holdings, "current_value")
    if numeric:
        return sorted(numeric, key=lambda item: item["current_value"], reverse=True)[:limit]
    return holdings[:limit]


def top_contributors(holdings: list[dict], limit: int = 5) -> list[dict]:
    numeric = _numeric_holdings(holdings, "ytd_pnl")
    return sorted(numeric, key=lambda item: item["ytd_pnl"], reverse=True)[:limit]


def top_detractors(holdings: list[dict], limit: int = 5) -> list[dict]:
    numeric = _numeric_holdings(holdings, "ytd_pnl")
    return sorted(numeric, key=lambda item: item["ytd_pnl"])[:limit]


def aggregate_exposure(holdings: list[dict], key: str, limit: int = 8) -> list[dict]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"current_value": 0.0, "ytd_pnl": 0.0})
    total = sum(float(item["current_value"]) for item in holdings if item.get("current_value") is not None)
    for holding in holdings:
        label = holding.get(key) or "Unclassified"
        if holding.get("current_value") is not None:
            grouped[label]["current_value"] += float(holding["current_value"])
        if holding.get("ytd_pnl") is not None:
            grouped[label]["ytd_pnl"] += float(holding["ytd_pnl"])

    rows = []
    for label, values in grouped.items():
        value = values["current_value"]
        pnl = values["ytd_pnl"]
        rows.append(
            {
                "name": label,
                "current_value": value,
                "current_value_display": _format_usd(value),
                "weight": (value / total) if total else None,
                "weight_display": f"{(value / total):.0%}" if total else MANUAL_LABEL,
                "ytd_pnl": pnl,
                "ytd_pnl_display": _format_usd(pnl, signed=True),
            }
        )
    return sorted(rows, key=lambda item: item["current_value"], reverse=True)[:limit]


def equity_monitor(holdings: list[dict]) -> dict:
    sector_exposure = aggregate_exposure(holdings, "sector")
    currency_exposure = aggregate_exposure(holdings, "currency")
    best = next(iter(top_contributors(holdings, 1)), None)
    worst = next(iter(top_detractors(holdings, 1)), None)
    largest_sector = next(iter(sector_exposure), None)
    largest_currency = next(iter(currency_exposure), None)
    total_value = sum(float(item["current_value"]) for item in holdings if item.get("current_value") is not None)
    total_pnl = sum(float(item["ytd_pnl"]) for item in holdings if item.get("ytd_pnl") is not None)
    missing_pricing_holdings = [item["holding"] for item in holdings if item.get("is_manual_pricing")]
    manual_priced_holdings = [item["holding"] for item in holdings if item.get("pricing_mode") == "manual" and item.get("has_usable_pricing")]
    return {
        "title": "Equity Holdings Monitor",
        "holdings_count": len(holdings),
        "usable_equity_pricing_count": len([item for item in holdings if item.get("has_usable_pricing")]),
        "manual_pricing_count": len(manual_priced_holdings),
        "missing_pricing_count": len(missing_pricing_holdings),
        "invalid_or_manual_holdings": missing_pricing_holdings,
        "total_equity_portfolio_value_usd": total_value,
        "total_ytd_equity_pnl_usd": total_pnl,
        "best_contributor": best["holding"] if best else None,
        "worst_contributor": worst["holding"] if worst else None,
        "largest_sector_exposure": largest_sector["name"] if largest_sector else None,
        "largest_currency_exposure": largest_currency["name"] if largest_currency else None,
        "kpis": [
            {"label": "Total Equity Portfolio Value", "value": _format_usd(total_value) if total_value else MANUAL_LABEL},
            {"label": "Total YTD Equity P&L", "value": _format_usd(total_pnl, signed=True) if total_pnl else MANUAL_LABEL},
            {"label": "Best Contributor", "value": best["holding"] if best else MANUAL_LABEL},
            {"label": "Worst Contributor", "value": worst["holding"] if worst else MANUAL_LABEL},
            {"label": "Largest Sector Exposure", "value": largest_sector["name"] if largest_sector else MANUAL_LABEL},
            {"label": "Largest Currency Exposure", "value": largest_currency["name"] if largest_currency else MANUAL_LABEL},
        ],
        "top_holdings": top_by_value(holdings, 8),
        "top_contributors": top_contributors(holdings, 5),
        "top_detractors": top_detractors(holdings, 5),
        "sector_exposure": sector_exposure,
        "currency_exposure": currency_exposure,
        "interpretation": (
            f"Equity exposure is concentrated in {largest_sector['name'] if largest_sector else 'unclassified sectors'} "
            f"and {largest_currency['name'] if largest_currency else 'unclassified currencies'}-denominated holdings. "
            f"YTD contribution is led by {best['holding'] if best else MANUAL_LABEL}, while "
            f"{worst['holding'] if worst else MANUAL_LABEL} is the largest detractor."
        ),
    }
