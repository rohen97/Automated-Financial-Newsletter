from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.io import project_path, write_json


MODEL_VERSION = "ngram-v1"
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9'-]*")
FALLBACK_SOURCES = {"sample data", "fallback source"}
BOILERPLATE_PHRASES = {
    "click here",
    "read more",
    "market update",
    "this week",
    "last week",
    "according to",
    "wolf research",
}
STOPWORDS = {
    "a",
    "about",
    "after",
    "again",
    "against",
    "all",
    "also",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "more",
    "most",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}
TOKEN_NORMALISATION = {
    "banks": "bank",
    "bonds": "bond",
    "companies": "company",
    "currencies": "currency",
    "cuts": "cut",
    "economies": "economy",
    "equities": "equity",
    "hikes": "hike",
    "investors": "investor",
    "markets": "market",
    "prices": "price",
    "rates": "rate",
    "stocks": "stock",
    "tariffs": "tariff",
    "yields": "yield",
}
DISPLAY_TOKENS = {
    "ai": "AI",
    "apac": "APAC",
    "bis": "BIS",
    "boj": "BoJ",
    "ecb": "ECB",
    "eu": "EU",
    "fed": "Fed",
    "fx": "FX",
    "gdp": "GDP",
    "imf": "IMF",
    "sgd": "SGD",
    "uk": "UK",
    "us": "US",
    "usd": "USD",
}


def build_narrative_monitor(
    articles: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
    history_path: str | Path | None = None,
    persist_history: bool = True,
) -> dict[str, Any]:
    settings = _settings(config)
    if not settings["enabled"]:
        return _empty_section("Narrative monitoring is disabled.")

    generated_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    period_end = generated_at.date().isoformat()
    documents = [_document(article) for article in articles if _is_usable_article(article)]
    documents = [document for document in documents if document["tokens"]]
    current = _aggregate(documents, settings["ngram_sizes"])

    target = _history_path(history_path or settings["history_path"])
    history = _load_history(target)
    prior_snapshots = [
        snapshot
        for snapshot in history.get("snapshots", [])
        if snapshot.get("period_end") != period_end
    ][-settings["baseline_periods"] :]

    rows = _trend_rows(current, prior_snapshots, settings)
    snapshot = _snapshot(period_end, generated_at, current, settings["max_history_phrases"])
    history_updated = False
    if documents:
        snapshots = [
            item
            for item in history.get("snapshots", [])
            if item.get("period_end") != period_end
        ]
        snapshots.append(snapshot)
        history = {"version": 1, "model_version": MODEL_VERSION, "snapshots": snapshots[-settings["max_history_periods"] :]}
        if persist_history:
            write_json(target, history)
            history_updated = True

    status_counts = dict(Counter(row["status"] for row in rows))
    source_count = len({document["source"] for document in documents})
    return {
        "title": "Narrative Monitor",
        "subtitle": "Themes gaining or losing attention across the aggregated news corpus.",
        "rows": rows,
        "document_count": len(documents),
        "source_count": source_count,
        "baseline_periods": len(prior_snapshots),
        "status_counts": status_counts,
        "history_updated": history_updated,
        "model_version": MODEL_VERSION,
        "generated_at": generated_at.isoformat(),
        "note": "Coverage momentum measures changes in news attention, not market direction or a trading signal.",
        "empty_message": "Not enough cross-source repetition was found to identify a reliable narrative this week.",
    }


def _settings(config: dict[str, Any] | None) -> dict[str, Any]:
    supplied = config or {}
    sizes = [int(value) for value in supplied.get("ngram_sizes", [2, 3]) if int(value) in {2, 3, 4}]
    return {
        "enabled": bool(supplied.get("enabled", True)),
        "history_path": supplied.get("history_path", "data/trends/ngram_history.json"),
        "ngram_sizes": sizes or [2, 3],
        "min_article_count": max(int(supplied.get("min_article_count", 2)), 1),
        "min_distinct_sources": max(int(supplied.get("min_distinct_sources", 2)), 1),
        "baseline_periods": max(int(supplied.get("baseline_periods", 8)), 1),
        "max_history_periods": max(int(supplied.get("max_history_periods", 12)), 2),
        "max_history_phrases": max(int(supplied.get("max_history_phrases", 500)), 25),
        "max_rows": max(int(supplied.get("max_rows", 6)), 1),
        "accelerating_threshold": float(supplied.get("accelerating_threshold", 1.5)),
        "fading_threshold": float(supplied.get("fading_threshold", 0.67)),
    }


def _is_usable_article(article: dict[str, Any]) -> bool:
    source = str(article.get("source") or "").strip().casefold()
    url = str(article.get("url") or "")
    text = f"{article.get('title', '')} {article.get('summary', '')}".strip()
    return bool(text) and source not in FALLBACK_SOURCES and "example.com/wolf-research" not in url


def _document(article: dict[str, Any]) -> dict[str, Any]:
    tags = " ".join(str(item) for item in article.get("tags", []) if item)
    entities = " ".join(str(item) for item in article.get("entities", []) if item)
    text = " ".join(
        str(value)
        for value in (
            article.get("title", ""),
            article.get("summary") or article.get("description", ""),
            tags,
            entities,
        )
        if value
    )
    source_quality = _bounded_float(article.get("source_quality_score"), 0.65)
    return {
        "tokens": _tokenise(text),
        "source": str(article.get("source") or "Unknown source").strip(),
        "title": str(article.get("title") or "Untitled").strip(),
        "region": str(article.get("region") or "Global").strip(),
        "category": str(article.get("category") or "Markets").strip(),
        "portfolio_relevant": bool(
            _bounded_float(article.get("portfolio_relevance_score"), 0.0) >= 0.6
            or any(article.get(field) for field in ("matched_holdings", "matched_issuers", "matched_sectors", "matched_currencies"))
        ),
        "weight": 0.5 + source_quality,
    }


def _tokenise(value: str) -> list[str]:
    tokens = []
    for raw in TOKEN_RE.findall(value):
        token = raw.lower().strip("'-")
        token = TOKEN_NORMALISATION.get(token, token)
        if len(token) >= 3 or token in DISPLAY_TOKENS:
            tokens.append(token)
    return tokens


def _aggregate(documents: list[dict[str, Any]], sizes: list[int]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    weighted: Counter[str] = Counter()
    sources: dict[str, set[str]] = defaultdict(set)
    regions: dict[str, Counter[str]] = defaultdict(Counter)
    categories: dict[str, Counter[str]] = defaultdict(Counter)
    examples: dict[str, list[str]] = defaultdict(list)
    portfolio_hits: Counter[str] = Counter()

    for document in documents:
        phrases = set(_ngrams(document["tokens"], sizes))
        for phrase in phrases:
            counts[phrase] += 1
            weighted[phrase] += document["weight"]
            sources[phrase].add(document["source"])
            regions[phrase][document["region"]] += 1
            categories[phrase][document["category"]] += 1
            if document["title"] not in examples[phrase] and len(examples[phrase]) < 3:
                examples[phrase].append(document["title"])
            if document["portfolio_relevant"]:
                portfolio_hits[phrase] += 1

    return {
        "document_count": len(documents),
        "source_count": len({document["source"] for document in documents}),
        "counts": counts,
        "weighted": weighted,
        "sources": sources,
        "regions": regions,
        "categories": categories,
        "examples": examples,
        "portfolio_hits": portfolio_hits,
    }


def _ngrams(tokens: list[str], sizes: list[int]):
    for size in sizes:
        for index in range(len(tokens) - size + 1):
            words = tokens[index : index + size]
            if words[0] in STOPWORDS or words[-1] in STOPWORDS:
                continue
            if sum(word not in STOPWORDS for word in words) < 2:
                continue
            phrase = " ".join(words)
            if any(blocked in phrase for blocked in BOILERPLATE_PHRASES):
                continue
            yield phrase


def _trend_rows(current: dict[str, Any], snapshots: list[dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    current_docs = max(int(current["document_count"]), 1)
    baseline = _baseline(snapshots)
    candidates = set()
    for phrase, count in current["counts"].items():
        if count >= settings["min_article_count"] and len(current["sources"][phrase]) >= settings["min_distinct_sources"]:
            candidates.add(phrase)
    if snapshots:
        for phrase, average_count in baseline["counts"].items():
            if (
                average_count >= settings["min_article_count"]
                and baseline["source_counts"].get(phrase, 0) >= settings["min_distinct_sources"]
            ):
                candidates.add(phrase)

    rows = []
    for phrase in candidates:
        count = int(current["counts"].get(phrase, 0))
        source_count = len(current["sources"].get(phrase, set()))
        current_share = count / current_docs
        baseline_share = baseline["shares"].get(phrase, 0.0)
        lift, momentum_score = _momentum(current_share, baseline_share, current_docs, bool(snapshots))
        status = _status(lift, count, baseline_share, bool(snapshots), settings)
        if status != "Fading" and (count < settings["min_article_count"] or source_count < settings["min_distinct_sources"]):
            continue
        score = _row_score(
            count=count,
            weighted=float(current["weighted"].get(phrase, 0.0)),
            source_count=source_count,
            current_share=current_share,
            baseline_share=baseline_share,
            momentum_score=momentum_score,
            status=status,
            phrase=phrase,
        )
        rows.append(
            {
                "phrase": _display_phrase(phrase),
                "phrase_key": phrase,
                "status": status,
                "momentum_score": round(momentum_score, 3),
                "momentum_display": _momentum_display(lift, status),
                "article_count": count,
                "source_count": source_count,
                "coverage_display": f"{count} article{'s' if count != 1 else ''} / {source_count} source{'s' if source_count != 1 else ''}",
                "current_share_pct": round(current_share * 100, 1),
                "baseline_share_pct": round(baseline_share * 100, 1),
                "regions": _top_labels(current["regions"].get(phrase, Counter())),
                "categories": _top_labels(current["categories"].get(phrase, Counter())),
                "portfolio_relevant": bool(current["portfolio_hits"].get(phrase, 0)),
                "trend_note": _trend_note(status, lift, count, source_count, len(snapshots)),
                "examples": current["examples"].get(phrase, []),
                "_score": score,
            }
        )

    rows.sort(key=lambda row: (row["_score"], row["article_count"], row["source_count"]), reverse=True)
    selected = []
    for row in rows:
        if any(_phrases_overlap(row["phrase_key"], existing["phrase_key"]) for existing in selected):
            continue
        selected.append(row)
        if len(selected) >= settings["max_rows"]:
            break
    for row in selected:
        row.pop("_score", None)
        row.pop("phrase_key", None)
    return selected


def _baseline(snapshots: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    if not snapshots:
        return {"counts": {}, "shares": {}, "source_counts": {}}
    count_totals: Counter[str] = Counter()
    share_totals: Counter[str] = Counter()
    source_totals: Counter[str] = Counter()
    for snapshot in snapshots:
        documents = max(int(snapshot.get("document_count") or 0), 1)
        for phrase, count in snapshot.get("phrase_counts", {}).items():
            count_totals[phrase] += float(count)
            share_totals[phrase] += float(count) / documents
        for phrase, count in snapshot.get("phrase_source_counts", {}).items():
            source_totals[phrase] += float(count)
    divisor = len(snapshots)
    return {
        "counts": {phrase: value / divisor for phrase, value in count_totals.items()},
        "shares": {phrase: value / divisor for phrase, value in share_totals.items()},
        "source_counts": {phrase: value / divisor for phrase, value in source_totals.items()},
    }


def _momentum(current_share: float, baseline_share: float, document_count: int, has_baseline: bool) -> tuple[float | None, float]:
    if not has_baseline:
        return None, 0.0
    smoothing = 0.5 / max(document_count, 1)
    lift = (current_share + smoothing) / (baseline_share + smoothing)
    return lift, math.log2(max(lift, 0.001))


def _status(
    lift: float | None,
    count: int,
    baseline_share: float,
    has_baseline: bool,
    settings: dict[str, Any],
) -> str:
    if not has_baseline:
        return "Establishing"
    if baseline_share == 0 and count > 0:
        return "Emerging"
    if count == 0 or (lift is not None and lift <= settings["fading_threshold"]):
        return "Fading"
    if lift is not None and lift >= settings["accelerating_threshold"]:
        return "Accelerating"
    return "Persistent"


def _row_score(**values: Any) -> float:
    source_bonus = 1 + 0.2 * max(int(values["source_count"]) - 1, 0)
    phrase_bonus = 1.06 if len(str(values["phrase"]).split()) == 3 else 1.0
    if values["status"] == "Fading":
        return float(values["baseline_share"]) * source_bonus * 0.65
    momentum_bonus = 1 + 0.18 * max(float(values["momentum_score"]), 0.0)
    quality = float(values["weighted"]) / max(int(values["count"]), 1)
    return float(values["current_share"]) * source_bonus * momentum_bonus * quality * phrase_bonus


def _momentum_display(lift: float | None, status: str) -> str:
    if lift is None:
        return "Baseline"
    if status == "Emerging":
        return "New"
    return f"{lift:.1f}x"


def _trend_note(status: str, lift: float | None, count: int, source_count: int, baseline_periods: int) -> str:
    coverage = f"{count} article{'s' if count != 1 else ''} across {source_count} source{'s' if source_count != 1 else ''}"
    if status == "Establishing":
        return f"{coverage.capitalize()}; the rolling baseline is being established."
    if status == "Emerging":
        return f"New versus the trailing {baseline_periods}-period baseline, with {coverage}."
    if status == "Accelerating":
        return f"Coverage is {lift:.1f}x the trailing baseline, with {coverage}."
    if status == "Fading":
        return f"Coverage has fallen to {lift:.1f}x the trailing baseline."
    return f"Coverage is close to its trailing baseline, with {coverage}."


def _top_labels(values: Counter[str], limit: int = 3) -> list[str]:
    return [label for label, _ in values.most_common(limit)]


def _display_phrase(phrase: str) -> str:
    return " ".join(DISPLAY_TOKENS.get(token, token.capitalize()) for token in phrase.split())


def _phrases_overlap(left: str, right: str) -> bool:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    intersection = len(left_tokens & right_tokens)
    return intersection / max(min(len(left_tokens), len(right_tokens)), 1) >= 0.67


def _snapshot(period_end: str, generated_at: datetime, current: dict[str, Any], limit: int) -> dict[str, Any]:
    ranked_phrases = sorted(
        current["counts"],
        key=lambda phrase: (current["weighted"][phrase], current["counts"][phrase]),
        reverse=True,
    )[:limit]
    return {
        "period_end": period_end,
        "generated_at": generated_at.isoformat(),
        "document_count": current["document_count"],
        "source_count": current["source_count"],
        "phrase_counts": {phrase: current["counts"][phrase] for phrase in ranked_phrases},
        "phrase_source_counts": {phrase: len(current["sources"][phrase]) for phrase in ranked_phrases},
        "weighted_counts": {phrase: round(current["weighted"][phrase], 4) for phrase in ranked_phrases},
    }


def _history_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_path(str(path))


def _load_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "model_version": MODEL_VERSION, "snapshots": []}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "model_version": MODEL_VERSION, "snapshots": []}
    if not isinstance(loaded, dict) or not isinstance(loaded.get("snapshots"), list):
        return {"version": 1, "model_version": MODEL_VERSION, "snapshots": []}
    return loaded


def _bounded_float(value: Any, default: float) -> float:
    try:
        return min(max(float(value), 0.0), 1.0)
    except (TypeError, ValueError):
        return default


def _empty_section(message: str) -> dict[str, Any]:
    return {
        "title": "Narrative Monitor",
        "subtitle": "Themes gaining or losing attention across the aggregated news corpus.",
        "rows": [],
        "document_count": 0,
        "source_count": 0,
        "baseline_periods": 0,
        "status_counts": {},
        "history_updated": False,
        "model_version": MODEL_VERSION,
        "note": "Coverage momentum measures changes in news attention, not market direction or a trading signal.",
        "empty_message": message,
    }
