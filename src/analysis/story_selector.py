from __future__ import annotations


STATUS_BOOSTS = {
    "accelerating": 0.12,
    "emerging": 0.09,
    "persistent": 0.05,
    "establishing": 0.03,
    "fading": 0.0,
}
TOPIC_STOPWORDS = {
    "about",
    "after",
    "amid",
    "before",
    "from",
    "into",
    "next",
    "over",
    "that",
    "their",
    "this",
    "what",
    "with",
}


def select_story_of_the_week(
    articles: list[dict],
    narrative_monitor: dict | None = None,
) -> dict:
    if not articles:
        return {
            "title": "No dominant story identified",
            "narrative": "Insufficient source material was available.",
            "implications": [],
            "sources": [],
        }
    candidates = [_story_candidate(article, narrative_monitor or {}) for article in articles]
    top_candidate = max(candidates, key=lambda item: item["editorial_score"])
    top = top_candidate["article"]
    return {
        "title": top["title"],
        "narrative": top.get("summary") or top["title"],
        "implications": _default_implications(top),
        "sources": [{"name": top.get("source", "Source"), "url": top.get("url")}],
        "selection_signal": top_candidate.get("selection_signal", {}),
    }


def _story_candidate(article: dict, monitor: dict) -> dict:
    title = str(article.get("title", ""))
    summary = str(article.get("summary", ""))
    title_text = title.casefold()
    summary_text = summary.casefold()
    metadata_text = " ".join(
        str(item) for item in [*article.get("tags", []), *article.get("entities", [])]
    ).casefold()
    matches = []
    for row in monitor.get("rows", []):
        phrase = str(row.get("phrase", "")).strip()
        phrase_text = phrase.casefold()
        match_field = ""
        match_factor = 1.0
        if phrase_text and (phrase_text in title_text or phrase_text in metadata_text):
            match_field = "title_or_entity"
        elif phrase_text and phrase_text in summary_text and _coherence_penalty(title, summary) == 0:
            match_field = "summary"
            match_factor = 0.5
        if match_field:
            status = str(row.get("status", "")).casefold()
            if status == "fading":
                continue
            source_count = min(int(row.get("source_count") or 0), 5)
            boost = (STATUS_BOOSTS.get(status, 0.0) + source_count * 0.008) * match_factor
            matches.append((boost, row, match_field))

    selection_signal = {}
    narrative_boost = 0.0
    if matches:
        narrative_boost, signal, match_field = max(matches, key=lambda item: item[0])
        selection_signal = {
            "phrase": signal.get("phrase"),
            "status": signal.get("status"),
            "source_count": signal.get("source_count", 0),
            "article_count": signal.get("article_count", 0),
            "boost": round(narrative_boost, 4),
            "match_field": match_field,
        }

    base_score = float(article.get("importance_score") or 0)
    coherence_penalty = _coherence_penalty(title, summary)
    return {
        "article": article,
        "editorial_score": round(base_score + narrative_boost - coherence_penalty, 4),
        "selection_signal": selection_signal,
    }


def _coherence_penalty(title: str, summary: str) -> float:
    title_terms = _topic_terms(title)
    summary_terms = _topic_terms(summary)
    if len(title_terms) < 2 or len(summary_terms) < 2:
        return 0.0
    return 0.0 if title_terms & summary_terms else 0.08


def _topic_terms(value: str) -> set[str]:
    words = {
        word.strip(".,:;!?()[]{}'\"").casefold()
        for word in value.split()
    }
    return {word for word in words if len(word) >= 4 and word not in TOPIC_STOPWORDS}


def _default_implications(article: dict) -> list[str]:
    text = f"{article.get('title', '')} {article.get('summary', '')}".casefold()
    if "digital euro" in text or "central bank digital currency" in text or "cbdc" in text:
        primary = (
            "The digital euro matters for European payments infrastructure, bank intermediation, "
            "and the transmission of ECB policy."
        )
    elif any(term in text for term in ("federal reserve", "central bank", "monetary policy", "yield")):
        primary = "The policy signal matters for discount rates, currencies, credit conditions, and equity valuation."
    elif any(term in text for term in ("brent", "crude", "oil price", "natural gas", "lng")):
        primary = "The move matters for inflation expectations, input costs, rates, airlines, and energy-sensitive assets."
    elif any(term in text for term in ("artificial intelligence", " ai ", "semiconductor", "chip")):
        primary = "The development matters for technology earnings, capital expenditure, power demand, and valuation risk."
    else:
        primary = "Monitor how the development changes policy expectations, market pricing, and cross-asset risk transmission."
    return [primary, "Treat this as analytical context, not an investment recommendation."]
