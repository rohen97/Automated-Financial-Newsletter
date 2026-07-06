from __future__ import annotations

from difflib import SequenceMatcher

from src.processing.clean import normalize_title


def title_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalize_title(left), normalize_title(right)).ratio()


def dedupe_articles(articles: list[dict], threshold: float = 0.90) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: list[str] = []
    deduped: list[dict] = []

    for article in articles:
        url = (article.get("url") or "").strip().lower()
        title = article.get("title") or ""
        normalized = normalize_title(title)
        if url and url in seen_urls:
            continue
        if normalized and normalized in seen_titles:
            continue
        if any(title_similarity(normalized, previous) >= threshold for previous in seen_titles):
            continue
        if url:
            seen_urls.add(url)
        if normalized:
            seen_titles.append(normalized)
        deduped.append(article)
    return deduped
