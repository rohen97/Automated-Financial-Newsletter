from __future__ import annotations

import csv
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.portfolio.equity import parse_money, parse_number, parse_percent
from src.utils.io import project_path


CLASSIFICATION = {
    "kfw": ("Government Agency", "EU"),
    "european investment bank": ("Supranational", "EU"),
    "asian development bank": ("Supranational", "APAC"),
    "singapore government": ("Sovereign", "APAC"),
    "housing & development board": ("Government Agency", "APAC"),
    "land transport authority": ("Government Agency", "APAC"),
    "microsoft corp": ("Corporate", "US"),
    "amazon.com inc": ("Corporate", "US"),
    "alphabet inc": ("Corporate", "US"),
    "apple inc": ("Corporate", "US"),
    "nvidia corp": ("Corporate", "US"),
    "home depot inc": ("Corporate", "US"),
    "cisco systems inc": ("Corporate", "US"),
    "roche holdings inc": ("Corporate", "EU"),
    "siemens financieringsmat": ("Corporate", "EU"),
    "bmw us capital llc": ("Corporate", "EU"),
    "singapore airlines ltd": ("Corporate", "APAC"),
    "international bank for reconstruction and development": ("Supranational", "Global"),
}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def classify_issuer(issuer: str) -> tuple[str, str]:
    key = issuer.strip().lower()
    if key in CLASSIFICATION:
        return CLASSIFICATION[key]
    if any(term in key for term in ("treasury", "government", "govt", "republic")):
        return "Sovereign", "Global"
    if any(term in key for term in ("bank", "insurance", "holdings")):
        return "Financial", "Global"
    if any(term in key for term in ("transport", "airlines", "airport")):
        return "Infrastructure / Transport", "APAC"
    if any(term in key for term in ("corp", "inc", "ltd", "llc", "plc", "capital")):
        return "Corporate", "Global"
    return "Unknown", "Global"


def _format_usd(value: float | None, *, signed: bool = False) -> str:
    if value is None:
        return "--"
    sign = ""
    if signed:
        sign = "+" if value > 0 else "-" if value < 0 else ""
    amount = abs(value)
    if amount >= 1_000_000:
        return f"{sign}USD {amount / 1_000_000:.1f}m"
    if amount >= 1_000:
        return f"{sign}USD {amount / 1_000:.1f}k"
    return f"{sign}USD {amount:,.0f}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "--"
    pct = value * 100 if abs(value) < 1 else value
    return f"{pct:+.2f}%"


def _parse_date(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return text


def load_fixed_income_issuers(path: str | Path = "data/portfolio/fixed_income_holdings.csv") -> list[dict]:
    target = Path(path)
    if not target.is_absolute():
        target = project_path(str(target))
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        positions = []
        for row in reader:
            issuer = _clean(row.get("issuer"))
            if not issuer:
                continue
            issuer_type, region = classify_issuer(issuer)
            positions.append(
                {
                    "issuer": issuer,
                    "isin": _clean(row.get("isin")),
                    "country": _clean(row.get("country")),
                    "bank": _clean(row.get("bank")),
                    "account_no": _clean(row.get("account_no")),
                    "held_by": _clean(row.get("held_by")),
                    "coupon": parse_percent(row.get("coupon")),
                    "maturity_date": _parse_date(row.get("maturity_date")),
                    "currency": _clean(row.get("currency")),
                    "notional_amount": parse_number(row.get("notional_amount")),
                    "equivalent_cost_usd": parse_money(row.get("equivalent_cost_usd")),
                    "market_value_usd": parse_money(row.get("market_value_usd")),
                    "accrued_interest_usd": parse_money(row.get("accrued_interest_usd")),
                    "total_value_usd": parse_money(row.get("total_value_usd")),
                    "gain_loss_usd": parse_money(row.get("gain_loss_usd")),
                    "gain_loss_pct": parse_percent(row.get("gain_loss_pct")),
                    "type": issuer_type,
                    "region": region,
                }
            )
    return positions


def _issuer_name(item: str | dict) -> str:
    return item if isinstance(item, str) else item.get("issuer", "")


def _position_mode(items: list[str | dict]) -> bool:
    return bool(items) and isinstance(items[0], dict)


def _aggregate_by(items: list[dict], key: str, limit: int = 8) -> list[dict]:
    total = sum(float(item.get("market_value_usd") or 0) for item in items)
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"market_value_usd": 0.0, "gain_loss_usd": 0.0, "count": 0})
    for item in items:
        label = item.get(key) or "Unknown"
        grouped[label]["market_value_usd"] += float(item.get("market_value_usd") or 0)
        grouped[label]["gain_loss_usd"] += float(item.get("gain_loss_usd") or 0)
        grouped[label]["count"] += 1
    rows = []
    for label, values in grouped.items():
        market_value = values["market_value_usd"]
        rows.append(
            {
                "name": label,
                "count": values["count"],
                "market_value_usd": market_value,
                "market_value_display": _format_usd(market_value),
                "weight": market_value / total if total else None,
                "weight_display": f"{market_value / total:.0%}" if total else "--",
                "gain_loss_usd": values["gain_loss_usd"],
                "gain_loss_display": _format_usd(values["gain_loss_usd"], signed=True),
            }
        )
    return sorted(rows, key=lambda item: item["market_value_usd"], reverse=True)[:limit]


def _maturity_bucket(maturity_date: str) -> str:
    if not maturity_date:
        return "Unknown"
    try:
        maturity = datetime.fromisoformat(maturity_date).date()
    except ValueError:
        return "Unknown"
    years = (maturity - date.today()).days / 365.25
    if years <= 1:
        return "0-1Y"
    if years <= 3:
        return "1-3Y"
    if years <= 5:
        return "3-5Y"
    return "5Y+"


def fixed_income_monitor(positions: list[str | dict]) -> dict:
    if not _position_mode(positions):
        issuers = [_issuer_name(item) for item in positions]
        counts = Counter(issuers)
        rows = []
        for issuer, count in counts.most_common():
            issuer_type, region = classify_issuer(issuer)
            rows.append(
                {
                    "issuer": issuer,
                    "count": count,
                    "type": issuer_type,
                    "region": region,
                    "notes": "Issuer-level only",
                }
            )
        return {
            "title": "Fixed Income Monitor",
            "mode": "issuer-only",
            "issuer_count": len(rows),
            "position_count": len(issuers),
            "rows": rows,
            "missing_bond_fields": ["coupon", "maturity", "yield", "duration", "rating", "currency", "market_value"],
            "note": (
                "Fixed income analytics are issuer-level only. Coupon, maturity, yield, duration, "
                "rating, currency, and market value are required for full bond risk analytics."
            ),
        }

    bond_positions = [item for item in positions if isinstance(item, dict)]
    issuer_rows = _aggregate_by(bond_positions, "issuer", 10)
    currency_exposure = _aggregate_by(bond_positions, "currency", 8)
    region_exposure = _aggregate_by(bond_positions, "region", 8)
    maturity_rows = _aggregate_by([{**item, "maturity_bucket": _maturity_bucket(item.get("maturity_date", ""))} for item in bond_positions], "maturity_bucket", 8)
    total_market_value = sum(float(item.get("market_value_usd") or 0) for item in bond_positions)
    total_gain_loss = sum(float(item.get("gain_loss_usd") or 0) for item in bond_positions)
    issuers = {item.get("issuer") for item in bond_positions if item.get("issuer")}
    return {
        "title": "Fixed Income Monitor",
        "mode": "position-level",
        "issuer_count": len(issuers),
        "position_count": len(bond_positions),
        "total_market_value_usd": total_market_value,
        "total_market_value_display": _format_usd(total_market_value),
        "total_gain_loss_usd": total_gain_loss,
        "total_gain_loss_display": _format_usd(total_gain_loss, signed=True),
        "rows": [
            {
                "issuer": row["name"],
                "count": row["count"],
                "type": classify_issuer(row["name"])[0],
                "region": classify_issuer(row["name"])[1],
                "market_value_usd": row["market_value_usd"],
                "market_value_display": row["market_value_display"],
                "gain_loss_usd": row["gain_loss_usd"],
                "gain_loss_display": row["gain_loss_display"],
                "notes": f"{row['weight_display']} of bond market value",
            }
            for row in issuer_rows
        ],
        "currency_exposure": currency_exposure,
        "region_exposure": region_exposure,
        "maturity_exposure": maturity_rows,
        "missing_bond_fields": ["yield", "duration", "rating"],
        "note": (
            "Fixed income analytics now use position-level coupon, maturity, currency, market value, "
            "accrued interest, and gain/loss fields. Yield, duration, and rating are still required "
            "for full bond risk analytics."
        ),
    }
