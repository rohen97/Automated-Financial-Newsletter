from __future__ import annotations

import os
from datetime import date

from src.charts.chart_renderer import chart_metadata_path, render_fred_chart
from src.charts.fred_chart_selector import select_fred_chart, update_selection_history
from src.fetchers.provider_audit import record_error
from src.utils.io import load_yaml


def build_chart_of_the_week(
    config: dict | None = None,
    articles: list[dict] | None = None,
    equity_monitor: dict | None = None,
) -> dict:
    chart_config = config or load_yaml("config/charts.yaml")
    if not chart_config.get("include_chart_of_the_week", True):
        return {}

    filename = chart_config.get("chart_image_embedding", {}).get("local_output_filename", "chart_of_the_week.png")
    try:
        selection = select_fred_chart(chart_config, articles=articles or [], equity_monitor=equity_monitor or {})
    except Exception as exc:
        record_error("fred", f"intelligent chart selector failed: {exc}")
        fallback_config = _fallback_config(chart_config)
        selection = select_fred_chart(fallback_config, articles=[], equity_monitor=equity_monitor or {})

    selected = selection["selected"]
    candidate = selected["candidate"]
    local_path = render_fred_chart(selected, filename)
    selection_score = selected["selection_score"]
    selection_reason = selection["reason"]
    if not os.getenv("PYTEST_CURRENT_TEST"):
        update_selection_history(candidate["id"], selection_score, selection_reason)

    latest_values = _latest_values(selected["rows_by_series"])
    series_used = candidate.get("series", [])
    transformation = candidate.get("transformation", {}) or {}
    summary = _summary(candidate, latest_values, selected)
    portfolio_relevance = _portfolio_relevance(candidate)

    return {
        "title": candidate.get("title", "Chart of the Week"),
        "subtitle": candidate.get("relevance", ""),
        "source_name": "FRED",
        "source_type": "macro_data",
        "chart_id": candidate["id"],
        "series_used": series_used,
        "transformation_used": transformation,
        "latest_values": latest_values,
        "unit_label": candidate.get("unit_label"),
        "lookback": f"{candidate.get('lookback_months')} months",
        "local_image_path": str(local_path),
        "render_metadata_path": str(chart_metadata_path(local_path)),
        "image_src": "chart_of_the_week.png",
        "email_image_src": "cid:chart_of_the_week",
        "summary": summary,
        "portfolio_relevance": portfolio_relevance,
        "market_signal_reason": selection_reason,
        "selection_score": selection_score,
        "fred_chart_scores": _score_table(selection["ranked"]),
        "generated_at": date.today().isoformat(),
        "original_url": _fred_url(series_used),
        "fallback_mode": False,
        "extraction_method": "fred_intelligent_selector",
        "copyright_note": "Generated internally from FRED observations.",
        "compliance_approved": True,
        "embedded_image": True,
        "chart_selection_history_updated": True,
    }


def _fallback_config(chart_config: dict) -> dict:
    default_id = chart_config.get("fred_chart_selector", {}).get("default_chart_id", "us_10y_yield")
    candidates = [item for item in chart_config.get("fred_chart_candidates", []) if item.get("id") == default_id]
    if not candidates:
        candidates = chart_config.get("fred_chart_candidates", [])[:1]
    return {**chart_config, "fred_chart_candidates": candidates}


def _latest_values(rows_by_series: dict[str, list[dict]]) -> dict[str, float]:
    values = {}
    for series_id, rows in rows_by_series.items():
        if rows:
            values[series_id] = rows[-1]["value"]
    return values


def _summary(candidate: dict, latest_values: dict[str, float], selected: dict) -> str:
    if not latest_values:
        return f"{candidate.get('title', 'The selected chart')} was selected from the FRED chart universe."
    values = ", ".join(f"{series}: {value:.2f}" for series, value in latest_values.items())
    score = selected.get("selection_score", 0)
    return f"The selected FRED chart highlights {candidate.get('relevance', 'current market conditions')}. Latest readings: {values}. Selection score: {score:.2f}."


def _portfolio_relevance(candidate: dict) -> str:
    chart_id = candidate.get("id")
    mapping = {
        "us_10y_yield": "Rates remain central for equity multiples, REITs, utilities, growth exposure, and FX translation risk.",
        "yield_curve": "The curve frames growth-cycle risk for financials, cyclicals, and credit-sensitive exposure.",
        "high_yield_spreads": "Credit spreads affect private-market liquidity, refinancing windows, and broad risk appetite.",
        "financial_stress": "Financial stress is a cross-asset drawdown and liquidity signal for portfolio risk controls.",
        "inflation_path": "Inflation affects central-bank policy, margins, airlines, utilities, and currency risk.",
        "labour_market": "Labour cooling matters for Fed policy, consumption, cyclicals, and travel-linked holdings.",
        "real_rates": "Real rates affect gold, long-duration equities, REITs, and discount-rate sensitive assets.",
        "policy_vs_inflation": "Policy versus inflation shows restrictiveness, rate-cut timing, USD pressure, and equity multiple risk.",
    }
    return mapping.get(chart_id, candidate.get("relevance", "Relevant for cross-asset portfolio context."))


def _score_table(ranked: list[dict]) -> list[dict]:
    rows = []
    for item in ranked:
        rows.append(
            {
                "chart_id": item["candidate"]["id"],
                "selection_score": item["selection_score"],
                "score_parts": {key: round(value, 4) for key, value in item["score_parts"].items()},
            }
        )
    return rows


def _fred_url(series_used: list[str]) -> str:
    if len(series_used) == 1:
        return f"https://fred.stlouisfed.org/series/{series_used[0]}"
    return "https://fred.stlouisfed.org/"
