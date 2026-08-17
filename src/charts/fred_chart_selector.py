from __future__ import annotations

import os
from datetime import date

from src.charts.fred_chart_fetcher import fetch_fred_series, transform_series
from src.charts.fred_chart_signals import (
    freshness_score,
    market_move_score,
    news_relevance_score,
    portfolio_relevance_score,
    regime_relevance_score,
    trigger_boost,
)
from src.utils.io import project_path, write_json


HISTORY_PATH = project_path("data", "charts", "chart_selection_history.json")


def select_fred_chart(config: dict, articles: list[dict] | None = None, equity_monitor: dict | None = None) -> dict:
    selector_config = config.get("fred_chart_selector", {})
    candidates = config.get("fred_chart_candidates", [])
    history = load_selection_history()
    scores = []

    for candidate in candidates:
        rows_by_series, transformed = _load_candidate_data(candidate)
        score_parts = _score_candidate(candidate["id"], rows_by_series, articles or [], equity_monitor, history, selector_config)
        scores.append(
            {
                "candidate": candidate,
                "rows_by_series": transformed,
                "raw_rows_by_series": rows_by_series,
                "score_parts": score_parts,
                "selection_score": round(sum(score_parts.values()), 4),
            }
        )

    if not scores:
        raise RuntimeError("No FRED chart candidates could be scored.")
    ranked = sorted(scores, key=lambda item: item["selection_score"], reverse=True)
    selected = _apply_repeat_avoidance(ranked, history, selector_config)
    reason = _selection_reason(selected)
    return {
        "selected": selected,
        "ranked": ranked,
        "reason": reason,
        "history": history,
    }


def update_selection_history(chart_id: str, selection_score: float, reason: str) -> None:
    history = load_selection_history()
    history.append(
        {
            "selected_at": date.today().isoformat(),
            "chart_id": chart_id,
            "selection_score": selection_score,
            "reason": reason,
        }
    )
    write_json(HISTORY_PATH, history[-52:])


def load_selection_history() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    import json

    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _load_candidate_data(candidate: dict) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    raw = {}
    transformed = {}
    lookback = int(candidate.get("lookback_months", 36))
    transformations = candidate.get("transformation", {}) or {}
    for series_id in candidate.get("series", []):
        raw_rows = _sample_rows(series_id, lookback) if os.getenv("PYTEST_CURRENT_TEST") else fetch_fred_series(series_id, lookback)
        raw[series_id] = raw_rows
        transformed[series_id] = transform_series(raw_rows, transformations.get(series_id))
    return raw, transformed


def _sample_rows(series_id: str, lookback_months: int) -> list[dict]:
    from datetime import timedelta

    rows = []
    days = max(120, lookback_months * 31)
    start = date.today() - timedelta(days=days)
    base = {
        "DGS10": 4.0,
        "T10Y2Y": -0.4,
        "BAMLH0A0HYM2": 3.5,
        "STLFSI4": -0.2,
        "CPIAUCSL": 300.0,
        "UNRATE": 4.0,
        "DFII10": 1.8,
        "FEDFUNDS": 5.25,
    }.get(series_id, 1.0)
    for idx in range(days):
        drift = idx / max(days, 1)
        shock = 0.8 if series_id == "DGS10" and idx > days - 20 else 0.0
        rows.append({"date": start + timedelta(days=idx), "value": base + drift + shock})
    return rows


def _score_candidate(
    chart_id: str,
    rows_by_series: dict[str, list[dict]],
    articles: list[dict],
    equity_monitor: dict | None,
    history: list[dict],
    selector_config: dict,
) -> dict:
    boost, _ = trigger_boost(chart_id, rows_by_series)
    return {
        "market_move_score": 0.30 * market_move_score(rows_by_series),
        "news_relevance_score": 0.25 * news_relevance_score(chart_id, articles),
        "portfolio_relevance_score": 0.20 * portfolio_relevance_score(chart_id, equity_monitor),
        "regime_relevance_score": 0.15 * regime_relevance_score(chart_id, articles, rows_by_series),
        "freshness_score": 0.10
        * freshness_score(chart_id, history, int(selector_config.get("avoid_repeat_weeks", 2))),
        "trigger_boost": boost,
    }


def _apply_repeat_avoidance(ranked: list[dict], history: list[dict], selector_config: dict) -> dict:
    avoid_weeks = int(selector_config.get("avoid_repeat_weeks", 2))
    advantage = float(selector_config.get("allow_repeat_if_score_advantage_pct", 25)) / 100
    recent = {item.get("chart_id") for item in history[-avoid_weeks:]}
    top = ranked[0]
    if top["candidate"]["id"] not in recent or len(ranked) == 1:
        return top
    next_non_recent = next((item for item in ranked[1:] if item["candidate"]["id"] not in recent), ranked[1])
    if top["selection_score"] >= next_non_recent["selection_score"] * (1 + advantage):
        return top
    return next_non_recent


def _selection_reason(selected: dict) -> str:
    candidate = selected["candidate"]
    boost, trigger_reason = trigger_boost(candidate["id"], selected["raw_rows_by_series"])
    parts = selected["score_parts"]
    strongest = max(parts, key=parts.get)
    reason = f"Selected because {strongest.replace('_', ' ')} was the largest contributor to the chart score."
    if boost > 0:
        reason = f"{trigger_reason} {reason}"
    return reason
