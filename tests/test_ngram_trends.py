from __future__ import annotations

import json
from datetime import datetime, timezone

from src.analysis.ngram_trends import build_narrative_monitor


def _article(title: str, source: str) -> dict:
    return {
        "title": title,
        "summary": title,
        "source": source,
        "url": f"https://{source.lower().replace(' ', '')}.example/news",
        "region": "Global",
        "category": "Macro",
        "source_quality_score": 0.8,
    }


def _config() -> dict:
    return {
        "ngram_sizes": [2],
        "min_article_count": 2,
        "min_distinct_sources": 2,
        "baseline_periods": 8,
        "max_history_periods": 12,
        "max_rows": 10,
    }


def test_first_run_establishes_baseline_and_persists_history(tmp_path):
    history_path = tmp_path / "history.json"
    section = build_narrative_monitor(
        [
            _article("Central bank policy shapes bond demand", "Reuters"),
            _article("Central bank policy shifts yield expectations", "Financial Times"),
        ],
        _config(),
        now=datetime(2026, 8, 10, tzinfo=timezone.utc),
        history_path=history_path,
    )

    assert section["history_updated"] is True
    assert section["baseline_periods"] == 0
    assert any(row["phrase"] == "Central Bank" and row["status"] == "Establishing" for row in section["rows"])
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(history["snapshots"]) == 1


def test_subsequent_run_classifies_accelerating_emerging_and_fading(tmp_path):
    history_path = tmp_path / "history.json"
    baseline = [
        _article("Credit spread pressure reaches lenders", "Reuters"),
        _article("Credit spread pressure reaches borrowers", "Financial Times"),
        _article("Central bank guidance shapes duration", "Bloomberg"),
        _article("Central bank guidance shapes currencies", "Marketaux"),
        _article("Copper demand steadies", "BIS"),
        _article("European growth slows", "ECB"),
    ]
    build_narrative_monitor(
        baseline,
        _config(),
        now=datetime(2026, 8, 3, tzinfo=timezone.utc),
        history_path=history_path,
    )
    current = [
        _article("Credit spread widens across banks", "Reuters"),
        _article("Credit spread widens across issuers", "Financial Times"),
        _article("Credit spread repricing reaches Europe", "Bloomberg"),
        _article("Credit spread repricing reaches Asia", "Marketaux"),
        _article("AI investment accelerates", "Tiingo"),
        _article("AI investment supports capex", "Seeking Alpha"),
    ]
    section = build_narrative_monitor(
        current,
        _config(),
        now=datetime(2026, 8, 10, tzinfo=timezone.utc),
        history_path=history_path,
    )

    rows = {row["phrase"]: row for row in section["rows"]}
    assert rows["Credit Spread"]["status"] == "Accelerating"
    assert rows["AI Investment"]["status"] == "Emerging"
    assert rows["Central Bank"]["status"] == "Fading"
    assert section["baseline_periods"] == 1


def test_single_source_repetition_is_filtered(tmp_path):
    section = build_narrative_monitor(
        [
            _article("Oil supply disruption lifts crude", "Reuters"),
            _article("Oil supply disruption raises inflation", "Reuters"),
            _article("Oil supply disruption reaches Asia", "Reuters"),
        ],
        _config(),
        now=datetime(2026, 8, 10, tzinfo=timezone.utc),
        history_path=tmp_path / "history.json",
    )

    assert section["rows"] == []


def test_same_period_rerun_replaces_history_snapshot(tmp_path):
    history_path = tmp_path / "history.json"
    articles = [
        _article("Labour market cooling affects rates", "BLS"),
        _article("Labour market cooling affects demand", "Reuters"),
    ]
    for hour in (8, 12):
        build_narrative_monitor(
            articles,
            _config(),
            now=datetime(2026, 8, 10, hour, tzinfo=timezone.utc),
            history_path=history_path,
        )

    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(history["snapshots"]) == 1


def test_publisher_names_are_filtered_from_narratives(tmp_path):
    history_path = tmp_path / "history.json"
    articles = [
        _article("Oil prices retreat after inflation data - Yahoo Finance", "Yahoo Finance"),
        _article("Oil prices rise as supply tightens - Reuters", "Reuters"),
        _article("Oil price volatility reaches Europe - Financial Times", "Financial Times"),
        _article("Wall Street watches oil prices", "MarketWatch"),
        _article("Wall Street weighs rate outlook", "Morningstar"),
    ]

    section = build_narrative_monitor(
        articles,
        _config(),
        now=datetime(2026, 8, 10, tzinfo=timezone.utc),
        history_path=history_path,
    )

    phrases = {row["phrase"] for row in section["rows"]}
    assert "Oil Price" in phrases
    assert "Yahoo Finance" not in phrases
    assert "Wall Street" not in phrases
    history = json.loads(history_path.read_text(encoding="utf-8"))
    stored_phrases = history["snapshots"][0]["phrase_counts"]
    assert all("yahoo finance" not in phrase for phrase in stored_phrases)
    assert all("wall street" not in phrase for phrase in stored_phrases)
