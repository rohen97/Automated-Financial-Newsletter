from __future__ import annotations

import re
from typing import Any

from src.llm.schemas import Newsletter
from src.render.assemble_newsletter import (
    _normalize_rendered_html,
    change_class,
    display_header_date,
    format_pct,
    issue_code,
    story_tags,
    unique_source_count,
)
from src.utils.io import project_path


PREFERRED_FX = ("USD/SGD", "AUD/USD", "EUR/USD", "DXY")
PREFERRED_COMMODITIES = ("Brent", "WTI", "Gold", "Copper")
REGION_ORDER = ("US", "EU", "UK", "APAC", "EMEA", "Global")
SAMPLE_SOURCE_NAMES = {"sample data", "fallback source"}


def render_review_v2_html(newsletter: Newsletter | dict[str, Any]) -> str:
    data = newsletter.model_dump(mode="json") if isinstance(newsletter, Newsletter) else newsletter
    template_path = project_path("templates", "newsletter_review_v2.html.j2")
    css_path = project_path("assets", "newsletter_review_v2.css")

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template(template_path.name)
    rendered = template.render(
        newsletter=data,
        view=_build_review_view(data),
        css=css_path.read_text(encoding="utf-8"),
        change_class=change_class,
        format_pct=format_pct,
        display_header_date=display_header_date,
        issue_code=issue_code,
        story_tags=story_tags,
        unique_source_count=unique_source_count,
    )
    return _normalize_rendered_html(rendered)


def _build_review_view(newsletter: dict[str, Any]) -> dict[str, Any]:
    sections = newsletter.get("sections", {})
    executive = sections.get("executive_snapshot", {})
    watchlist = sections.get("portfolio_watchlist", {})
    story = sections.get("story_of_the_week", {})
    equity = sections.get("equity_holdings_monitor", {})

    signals = _select_signals(executive.get("signals", []))
    macro_signal = next((item for item in signals if str(item.get("label", "")).lower() == "macro"), None)
    if macro_signal and story.get("narrative"):
        macro_signal["detail"] = _first_sentences(str(story["narrative"]), 2, 260)

    portfolio_signal = next(
        (item for item in signals if str(item.get("label", "")).lower() == "portfolio"), None
    )
    if portfolio_signal and equity.get("interpretation"):
        portfolio_signal["detail"] = _first_sentences(str(equity["interpretation"]), 2, 260)
        sector = _first(equity.get("sector_exposure", [])).get("name")
        currency = _first(equity.get("currency_exposure", [])).get("name")
        if sector and currency:
            portfolio_signal["headline"] = f"{sector} and {currency} dominate portfolio risk"
        portfolio_signal["source"] = None

    return {
        "signals": signals,
        "story": _story_view(story, watchlist.get("rows", [])),
        "chart": _chart_view(sections.get("chart_of_the_week", {})),
        "fx_rows": _preferred_market_rows(sections.get("fx_markets", {}).get("rows", []), PREFERRED_FX),
        "commodity_rows": _preferred_market_rows(
            sections.get("commodities", {}).get("rows", []), PREFERRED_COMMODITIES
        ),
        "sector_rows": _sector_snapshot(sections.get("sector_scoreboard", {}).get("regions", [])),
        "portfolio_metrics": _portfolio_metrics(equity),
        "portfolio_interpretation": equity.get("interpretation", ""),
        "watch_rows": watchlist.get("rows", [])[:3],
        "headlines": _global_scan(
            sections.get("regional_headlines", {}).get("regions", []),
            feature_title=str(story.get("title", "")),
        ),
    }


def _select_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not signals:
        return []

    selected: list[dict[str, Any]] = []
    for label in ("Macro", "Portfolio"):
        match = next((item for item in signals if str(item.get("label", "")).lower() == label.lower()), None)
        if match:
            selected.append(match)

    risk_weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    remaining = [item for item in signals if item not in selected]
    remaining.sort(key=lambda item: risk_weight.get(str(item.get("risk", "")).upper(), 0), reverse=True)

    insert_at = 1 if selected else 0
    if remaining:
        selected.insert(insert_at, remaining[0])
    for item in signals:
        if item not in selected and len(selected) < 3:
            selected.append(item)

    cleaned = []
    for item in selected[:3]:
        copy = dict(item)
        copy["detail"] = _clean_excerpt(str(copy.get("detail", "")), 260)
        source = copy.get("source") or {}
        if str(source.get("name", "")).lower() in SAMPLE_SOURCE_NAMES:
            copy["source"] = None
        cleaned.append(copy)
    return cleaned


def _story_view(story: dict[str, Any], watch_rows: list[dict[str, Any]]) -> dict[str, Any]:
    implications = story.get("implications", [])
    first_watch = watch_rows[0] if watch_rows else {}
    watch_text = ""
    if first_watch:
        watch_text = f"{first_watch.get('event', '')}: {first_watch.get('portfolio_relevance', '')}".strip(": ")
    return {
        "title": story.get("title", "No material feature selected"),
        "view": story.get("narrative", "No material feature narrative available."),
        "why": implications[0] if implications else "Monitor cross-asset transmission and portfolio relevance.",
        "watch": watch_text or "Watch incoming macro data and changes in market pricing.",
        "sources": _real_sources(story.get("sources", [])),
    }


def _preferred_market_rows(rows: list[dict[str, Any]], preferred: tuple[str, ...]) -> list[dict[str, Any]]:
    by_label = {str(row.get("label", "")).casefold(): row for row in rows}
    selected = [by_label[label.casefold()] for label in preferred if label.casefold() in by_label]
    selected.extend(row for row in rows if row not in selected)
    return selected[:4]


def _sector_snapshot(regions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for block in regions:
        rows = [row for row in block.get("rows", []) if isinstance(row.get("one_week"), (int, float))]
        if not rows:
            continue
        leader = max(rows, key=lambda row: row["one_week"])
        laggard = min(rows, key=lambda row: row["one_week"])
        advancing = sum(1 for row in rows if row["one_week"] > 0)
        summaries.append(
            {
                "label": block.get("label") or block.get("region") or "Regional markets",
                "leader": leader.get("sector", "-"),
                "leader_change": leader["one_week"],
                "laggard": laggard.get("sector", "-"),
                "laggard_change": laggard["one_week"],
                "breadth": f"{advancing}/{len(rows)} advancing",
                "signature": (
                    leader.get("sector"),
                    round(float(leader["one_week"]), 4),
                    laggard.get("sector"),
                    round(float(laggard["one_week"]), 4),
                    advancing,
                    len(rows),
                ),
            }
        )

    signatures = {item["signature"] for item in summaries}
    if len(summaries) > 1 and len(signatures) == 1:
        summary = dict(summaries[0])
        summary["label"] = "Regional proxy"
        summary["note"] = "Distinct regional readings were unavailable in this source run."
        return [summary]
    return summaries[:3]


def _portfolio_metrics(equity: dict[str, Any]) -> list[dict[str, Any]]:
    contributor = _first(equity.get("top_contributors", []))
    detractor = _first(equity.get("top_detractors", []))
    sector = _first(equity.get("sector_exposure", []))
    currency = _first(equity.get("currency_exposure", []))
    metrics = [
        {
            "label": "Best contributor",
            "value": contributor.get("holding", "Not available"),
            "detail": contributor.get("ytd_pnl_display", ""),
            "tone": "positive",
        },
        {
            "label": "Largest detractor",
            "value": detractor.get("holding", "Not available"),
            "detail": detractor.get("ytd_pnl_display", ""),
            "tone": "negative",
        },
        {
            "label": "Sector concentration",
            "value": sector.get("name", "Not available"),
            "detail": sector.get("weight_display", ""),
            "tone": "neutral",
        },
        {
            "label": "Currency concentration",
            "value": currency.get("name", "Not available"),
            "detail": currency.get("weight_display", ""),
            "tone": "neutral",
        },
    ]
    return metrics


def _global_scan(regions: list[dict[str, Any]], feature_title: str = "") -> list[dict[str, Any]]:
    by_region = {str(group.get("region", "")): group for group in regions}
    selected = []
    for region in REGION_ORDER:
        headlines = by_region.get(region, {}).get("headlines", [])
        if headlines:
            item = max(headlines, key=lambda candidate: _headline_score(candidate, region, feature_title))
            if _headline_score(item, region, feature_title) >= 2:
                item = dict(item)
                item["headline"] = _shorten(str(item.get("headline", "")), 108)
                selected.append({"region": region, **item})
                continue
        if not headlines or _headline_score(item, region, feature_title) < 2:
            selected.append(
                {
                    "region": region,
                    "headline": "No material market update captured.",
                    "source": "Source monitor",
                    "category": "Monitoring",
                    "url": "",
                }
            )
    return selected


def _headline_score(item: dict[str, Any], region: str = "Global", feature_title: str = "") -> int:
    text = str(item.get("headline", "")).lower()
    market_terms = (
        "inflation",
        "rate",
        "fed",
        "central bank",
        "growth",
        "market",
        "bank",
        "debt",
        "trade",
        "tariff",
        "oil",
        "energy",
        "currency",
        "econom",
        "jobs",
        "employment",
        "yield",
        "credit",
        "debt",
        "technology",
        "earnings",
        "china",
        "yen",
        "intervention",
        "reserves",
        "cpi",
    )
    low_signal_terms = (
        "concert",
        "announces approval of the application",
        "requests comment",
        "proposal to modernize",
        "public comment",
    )
    region_terms = {
        "US": ("united states", "u.s.", "federal reserve", "fed ", "treasury", "wall street"),
        "EU": ("europe", "european", "eurozone", "ecb", "germany", "france", "renminbi"),
        "UK": ("united kingdom", "britain", "british", "bank of england", "boe", "sterling", "gilt"),
        "APAC": ("asia", "china", "japan", "singapore", "india", "australia", "yen", "yuan"),
        "EMEA": ("middle east", "africa", "iran", "hormuz", "gulf", "saudi"),
        "Global": ("global", "world", "cross-asset", "gold", "commodity"),
    }
    score = sum(2 for term in market_terms if term in text)
    score -= sum(8 for term in low_signal_terms if term in text)
    has_region_signal = any(_contains_term(text, term) for term in region_terms.get(region, ()))
    score += 3 if has_region_signal else (-6 if region != "Global" else 0)
    if feature_title and _normalise_title(text) == _normalise_title(feature_title):
        score -= 10
    if item.get("url"):
        score += 1
    return score


def _normalise_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _contains_term(text: str, term: str) -> bool:
    clean_term = term.strip().lower()
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(clean_term)}(?![a-z0-9])", text))


def _real_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        source
        for source in sources
        if str(source.get("name", "")).lower() not in SAMPLE_SOURCE_NAMES and source.get("url")
    ]


def _chart_view(chart: dict[str, Any]) -> dict[str, Any]:
    title = re.sub(r"^Chart of the Week:\s*", "", str(chart.get("title", "")), flags=re.IGNORECASE)
    readings = []
    units = str(chart.get("unit_label") or "")
    labels = {
        "DGS10": "US 10Y yield",
        "T10Y2Y": "10Y-2Y Treasury spread",
        "BAMLH0A0HYM2": "US high-yield spread",
        "STLFSI4": "St. Louis Financial Stress Index",
        "CPIAUCSL": "US CPI",
        "UNRATE": "US unemployment rate",
        "DFII10": "US 10Y real yield",
        "FEDFUNDS": "Fed Funds rate",
    }
    for series_id in chart.get("series_used", []):
        value = chart.get("latest_values", {}).get(series_id)
        if isinstance(value, (int, float)):
            suffix = "%" if units in {"%", "% YoY"} else ""
            readings.append(f"{labels.get(series_id, series_id)} {value:.2f}{suffix}")
    summary = str(chart.get("summary") or "")
    if readings:
        summary = f"Latest reading: {', '.join(readings)}."
    else:
        summary = re.sub(r"\s*Selection score:.*$", "", summary).strip()
    return {
        "title": title or "Current macro signal",
        "summary": summary,
        "key_read": chart.get("portfolio_relevance") or chart.get("market_signal_reason"),
    }


def _first(items: list[dict[str, Any]]) -> dict[str, Any]:
    return items[0] if items else {}


def _shorten(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rsplit(" ", 1)[0] + "..."


def _clean_excerpt(value: str, limit: int) -> str:
    value = _shorten(value, limit)
    if value.endswith((".", "!", "?", "...")):
        return value
    sentence_stops = list(re.finditer(r"[.!?](?=\s|$)", value))
    if sentence_stops and sentence_stops[-1].start() >= 80:
        return value[: sentence_stops[-1].end()]
    return value.rstrip(" ,;:") + "."


def _first_sentences(value: str, count: int, limit: int) -> str:
    value = " ".join(value.split())
    stops = list(re.finditer(r"[.!?](?=\s|$)", value))
    end = stops[count - 1].end() if len(stops) >= count else len(value)
    return _shorten(value[:end], limit)
