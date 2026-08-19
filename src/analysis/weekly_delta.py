from __future__ import annotations

from typing import Any


def build_weekly_delta(
    macro_rows: list[dict],
    fx_rows: list[dict],
    commodity_rows: list[dict],
    sector_section: dict,
) -> dict:
    rows = [
        _yield_signal(macro_rows),
        _financial_conditions_signal(macro_rows),
        _market_signal(fx_rows, "DXY"),
        _market_signal(commodity_rows, "Brent"),
        _breadth_signal(sector_section),
    ]
    usable = [row for row in rows if row]

    if len(usable) < 5:
        for label in ("Gold", "USD/SGD", "WTI"):
            source_rows = commodity_rows if label in {"Gold", "WTI"} else fx_rows
            candidate = _market_signal(source_rows, label)
            if candidate and all(row["signal"] != candidate["signal"] for row in usable):
                usable.append(candidate)
            if len(usable) >= 5:
                break

    sources = {
        str(row.get("source", {}).get("name", "")).strip()
        for row in usable
        if row.get("source", {}).get("name")
    }
    return {
        "title": "What Changed This Week",
        "subtitle": "Five observable shifts in rates, currencies, commodities, and market breadth.",
        "rows": usable[:5],
        "source_count": len(sources),
        "note": "Weekly changes use the latest available provider observations; direction labels describe market conditions, not recommendations.",
        "empty_message": "No verified weekly market changes were available from configured sources.",
    }


def build_dislocation_watch(
    macro_rows: list[dict],
    fx_rows: list[dict],
    commodity_rows: list[dict],
    sector_section: dict,
) -> dict:
    candidates = []
    yield_change_bp = _macro_change(macro_rows, "DGS10", multiplier=100)
    dxy = _find_market_row(fx_rows, "DXY")
    gold = _find_market_row(commodity_rows, "Gold")
    brent = _find_market_row(commodity_rows, "Brent")
    us_energy = _find_sector_row(sector_section, "US", "Energy")

    dxy_change = _number(dxy.get("one_week_change")) if dxy else None
    if (
        yield_change_bp is not None
        and dxy_change is not None
        and abs(yield_change_bp) >= 4
        and abs(dxy_change) >= 0.15
        and yield_change_bp * dxy_change < 0
    ):
        candidates.append(
            {
                "score": abs(yield_change_bp) / 10 + abs(dxy_change),
                "label": "Rates / FX",
                "title": "Treasury yields and the dollar diverged",
                "observation": (
                    f"The US 10Y yield moved {_format_bp(yield_change_bp)} while DXY moved "
                    f"{_format_pct(dxy_change)} over the week."
                ),
                "why_it_matters": "Rate differentials did not translate cleanly into dollar direction, signalling that growth, positioning, or risk flows may be dominating the usual relationship.",
                "affected_assets": "Rates, FX, global equities",
                "sources": _sources(_macro_row(macro_rows, "DGS10"), dxy),
            }
        )

    gold_change = _number(gold.get("one_week_change")) if gold else None
    if (
        yield_change_bp is not None
        and gold_change is not None
        and abs(yield_change_bp) >= 4
        and abs(gold_change) >= 1
        and yield_change_bp * gold_change > 0
    ):
        direction = "rose despite higher" if gold_change > 0 else "fell despite lower"
        candidates.append(
            {
                "score": abs(yield_change_bp) / 10 + abs(gold_change),
                "label": "Rates / Gold",
                "title": "Gold resisted its usual yield relationship",
                "observation": (
                    f"Gold {direction} Treasury yields: gold moved {_format_pct(gold_change)} as the "
                    f"US 10Y yield changed {_format_bp(yield_change_bp)}."
                ),
                "why_it_matters": "Safe-haven, inflation, or reserve-demand flows appear strong enough to offset the normal opportunity-cost effect from yields.",
                "affected_assets": "Gold, rates, USD",
                "sources": _sources(_macro_row(macro_rows, "DGS10"), gold),
            }
        )

    brent_change = _number(brent.get("one_week_change")) if brent else None
    energy_change = _number(us_energy.get("one_week")) if us_energy else None
    if (
        brent_change is not None
        and energy_change is not None
        and abs(brent_change) >= 1
        and abs(energy_change) >= 1
        and brent_change * energy_change < 0
    ):
        candidates.append(
            {
                "score": abs(brent_change) + abs(energy_change),
                "label": "Oil / Equities",
                "title": "Oil and energy equities moved apart",
                "observation": (
                    f"Brent moved {_format_pct(brent_change)} while US energy equities moved "
                    f"{_format_pct(energy_change)} over the week."
                ),
                "why_it_matters": "The equity response suggests earnings expectations, costs, or positioning are offsetting the direct commodity-price signal.",
                "affected_assets": "Energy equities, oil, inflation hedges",
                "sources": _sources(brent, us_energy),
            }
        )

    breadth = _regional_breadth(sector_section)
    if len(breadth) >= 2:
        strongest = max(breadth, key=lambda item: item["ratio"])
        weakest = min(breadth, key=lambda item: item["ratio"])
        gap = strongest["ratio"] - weakest["ratio"]
        if gap >= 0.4:
            candidates.append(
                {
                    "score": gap * 5,
                    "label": "Regional Breadth",
                    "title": "Regional participation split widened",
                    "observation": (
                        f"{strongest['label']} recorded {strongest['advancing']}/{strongest['total']} advancing "
                        f"sectors versus {weakest['advancing']}/{weakest['total']} in {weakest['label']}."
                    ),
                    "why_it_matters": "The headline equity signal is masking materially different regional participation and concentration risk.",
                    "affected_assets": "Regional equities, sector allocation, FX",
                    "sources": strongest["sources"] + [
                        source for source in weakest["sources"] if source not in strongest["sources"]
                    ],
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    items = []
    for item in candidates[:2]:
        clean = dict(item)
        clean.pop("score", None)
        items.append(clean)
    return {
        "title": "Dislocation Watch",
        "subtitle": "Cross-asset relationships that broke from their usual directional pattern.",
        "items": items,
        "empty_message": "No material cross-asset dislocation met the configured thresholds this week.",
        "note": "Rules are deterministic and threshold-based; an identified divergence is a monitoring signal, not a trade recommendation.",
    }


def _yield_signal(rows: list[dict]) -> dict | None:
    row = _macro_row(rows, "DGS10")
    change_bp = _macro_change(rows, "DGS10", multiplier=100)
    if not row or change_bp is None:
        return None
    if change_bp >= 4:
        state, tone = "Tightening", "negative"
        interpretation = "Higher long-end yields increased discount-rate pressure across equities and credit."
    elif change_bp <= -4:
        state, tone = "Easing", "positive"
        interpretation = "Lower long-end yields eased discount-rate pressure for duration-sensitive assets."
    else:
        state, tone = "Stable", "neutral"
        interpretation = "Long-end yields were broadly stable, limiting the weekly discount-rate impulse."
    return _delta_row(
        "US 10Y yield",
        str(row.get("value", "-")),
        change_bp,
        _format_bp(change_bp),
        state,
        tone,
        interpretation,
        row.get("source", {}),
    )


def _financial_conditions_signal(rows: list[dict]) -> dict | None:
    row = _macro_row(rows, "NFCI")
    change = _macro_change(rows, "NFCI")
    if not row or change is None:
        return None
    if abs(change) < 0.005:
        change = 0.0
    if change >= 0.03:
        state, tone = "Tighter", "negative"
        interpretation = "Financial conditions tightened, raising the hurdle for credit and risk assets."
    elif change <= -0.03:
        state, tone = "Looser", "positive"
        interpretation = "Financial conditions eased, improving the near-term liquidity backdrop for risk assets."
    else:
        state, tone = "Stable", "neutral"
        interpretation = "Financial conditions changed little and did not add a strong liquidity impulse."
    return _delta_row(
        "US financial conditions",
        str(row.get("value", "-")),
        change,
        f"{change:+.2f}" if change else "0.00",
        state,
        tone,
        interpretation,
        row.get("source", {}),
    )


def _market_signal(rows: list[dict], label: str) -> dict | None:
    row = _find_market_row(rows, label)
    if not row:
        return None
    change = _number(row.get("one_week_change"))
    last = _number(row.get("last"))
    if change is None or last is None:
        return None

    if label == "DXY":
        if change >= 0.25:
            state, tone = "USD firmer", "negative"
            interpretation = "A firmer dollar tightened the external backdrop for commodities and non-US risk assets."
        elif change <= -0.25:
            state, tone = "USD softer", "positive"
            interpretation = "A softer dollar eased translation and funding pressure outside the United States."
        else:
            state, tone = "Range-bound", "neutral"
            interpretation = "Broad dollar direction was muted and offered little cross-asset impulse."
    elif label in {"Brent", "WTI"}:
        if change >= 1.5:
            state, tone = "Inflationary", "negative"
            interpretation = "Higher crude prices increased the near-term inflation and input-cost signal."
        elif change <= -1.5:
            state, tone = "Disinflationary", "positive"
            interpretation = "Lower crude prices reduced the near-term inflation and input-cost signal."
        else:
            state, tone = "Balanced", "neutral"
            interpretation = "Crude prices were stable enough to leave the inflation impulse broadly unchanged."
    elif label == "Gold":
        state = "Safe-haven bid" if change >= 1 else "Risk premium eased" if change <= -1 else "Stable"
        tone = "negative" if change >= 1 else "positive" if change <= -1 else "neutral"
        interpretation = "Gold's weekly move reflects the balance between yields, USD direction, and defensive demand."
    else:
        state = "Higher" if change > 0.25 else "Lower" if change < -0.25 else "Stable"
        tone = "positive" if change > 0.25 else "negative" if change < -0.25 else "neutral"
        interpretation = str(row.get("driver_1w") or row.get("driver") or "Weekly market direction was limited.")

    return _delta_row(
        label,
        _format_level(label, last),
        change,
        _format_pct(change),
        state,
        tone,
        interpretation,
        row.get("source", {}),
    )


def _breadth_signal(section: dict) -> dict | None:
    us = next((item for item in _regional_breadth(section) if item["region"] == "US"), None)
    if not us:
        return None
    net = us["advancing"] - (us["total"] - us["advancing"])
    if us["ratio"] >= 0.6:
        state, tone = "Broadening", "positive"
        interpretation = "Most US sectors advanced, indicating broader participation beyond a narrow leadership group."
    elif us["ratio"] <= 0.4:
        state, tone = "Narrowing", "negative"
        interpretation = "Fewer US sectors advanced, increasing dependence on concentrated leadership."
    else:
        state, tone = "Mixed", "neutral"
        interpretation = "US sector participation was balanced and offered no decisive breadth signal."
    return _delta_row(
        "US sector breadth",
        f"{us['advancing']}/{us['total']} advancing",
        float(net),
        f"{net:+d} net",
        state,
        tone,
        interpretation,
        us["sources"][0] if us["sources"] else {},
    )


def _delta_row(
    signal: str,
    current_display: str,
    weekly_change_value: float,
    weekly_change_display: str,
    state: str,
    tone: str,
    interpretation: str,
    source: dict,
) -> dict:
    return {
        "signal": signal,
        "current_display": current_display,
        "weekly_change_value": round(float(weekly_change_value), 4),
        "weekly_change_display": weekly_change_display,
        "state": state,
        "tone": tone,
        "interpretation": interpretation,
        "source": source or {},
    }


def _macro_row(rows: list[dict], series_id: str) -> dict | None:
    return next((row for row in rows if str(row.get("series_id", "")).upper() == series_id), None)


def _macro_change(rows: list[dict], series_id: str, multiplier: float = 1) -> float | None:
    row = _macro_row(rows, series_id)
    value = _number(row.get("weekly_change")) if row else None
    return value * multiplier if value is not None else None


def _find_market_row(rows: list[dict], label: str) -> dict | None:
    return next((row for row in rows if str(row.get("label", "")).casefold() == label.casefold()), None)


def _find_sector_row(section: dict, region: str, sector: str) -> dict | None:
    for block in section.get("regions", []):
        if str(block.get("region", "")).casefold() != region.casefold():
            continue
        return next(
            (row for row in block.get("rows", []) if str(row.get("sector", "")).casefold() == sector.casefold()),
            None,
        )
    return None


def _regional_breadth(section: dict) -> list[dict[str, Any]]:
    result = []
    for block in section.get("regions", []):
        rows = [row for row in block.get("rows", []) if _number(row.get("one_week")) is not None]
        if not rows:
            continue
        advancing = sum(1 for row in rows if float(row["one_week"]) > 0)
        sources = []
        for row in rows:
            source = row.get("source", {})
            if source and source not in sources:
                sources.append(source)
        result.append(
            {
                "region": str(block.get("region") or ""),
                "label": str(block.get("label") or block.get("region") or "Regional markets"),
                "advancing": advancing,
                "total": len(rows),
                "ratio": advancing / len(rows),
                "sources": sources,
            }
        )
    return result


def _sources(*rows: dict | None) -> list[dict]:
    sources = []
    for row in rows:
        source = (row or {}).get("source", {})
        if source and source not in sources:
            sources.append(source)
    return sources


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _format_bp(value: float) -> str:
    return f"{value:+.0f}bp"


def _format_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _format_level(label: str, value: float) -> str:
    if label in {"Brent", "WTI", "Gold"}:
        return f"${value:,.2f}"
    if "/" in label:
        return f"{value:.4f}"
    return f"{value:.2f}"
