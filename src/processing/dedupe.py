from __future__ import annotations

from collections import Counter, defaultdict
from difflib import SequenceMatcher
import math

from src.processing.clean import normalize_title


STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def title_similarity(left: str, right: str) -> float:
    return _normalized_similarity(normalize_title(left), normalize_title(right))


def dedupe_articles(articles: list[dict], threshold: float = 0.90) -> list[dict]:
    seen_urls: set[str] = set()
    seen_title_set: set[str] = set()
    seen_titles: list[str] = []
    seen_tokens: list[set[str]] = []
    token_index: dict[str, set[int]] = defaultdict(set)
    deduped: list[dict] = []

    # Grain remains one row per article. Fuzzy matching only fans out to titles
    # sharing meaningful tokens, instead of comparing every article pair.
    for article in articles:
        url = (article.get("url") or "").strip().lower()
        title = article.get("title") or ""
        normalized = normalize_title(title)
        if url and url in seen_urls:
            continue
        if normalized and normalized in seen_title_set:
            continue
        tokens = _meaningful_tokens(normalized)
        if _has_similar_title(
            normalized,
            tokens,
            seen_titles,
            seen_tokens,
            token_index,
            threshold,
        ):
            continue
        if url:
            seen_urls.add(url)
        if normalized:
            title_index = len(seen_titles)
            seen_title_set.add(normalized)
            seen_titles.append(normalized)
            seen_tokens.append(tokens)
            for token in tokens:
                token_index[token].add(title_index)
        deduped.append(article)
    return deduped


def _has_similar_title(
    normalized: str,
    tokens: set[str],
    seen_titles: list[str],
    seen_tokens: list[set[str]],
    token_index: dict[str, set[int]],
    threshold: float,
) -> bool:
    if not normalized or not seen_titles:
        return False
    candidate_counts: Counter[int] = Counter()
    for token in tokens:
        candidate_counts.update(token_index.get(token, ()))
    if not tokens:
        candidate_counts.update(range(len(seen_titles)))

    for index, shared_count in candidate_counts.items():
        previous_tokens = seen_tokens[index]
        minimum_tokens = min(len(tokens), len(previous_tokens))
        required_overlap = 1 if minimum_tokens <= 3 else math.ceil(minimum_tokens * 0.5)
        if shared_count < required_overlap:
            continue
        if _normalized_similarity(normalized, seen_titles[index], threshold) >= threshold:
            return True
    return False


def _normalized_similarity(left: str, right: str, threshold: float = 0.0) -> float:
    if not left or not right:
        return 0.0
    matcher = SequenceMatcher(None, left, right)
    if threshold and matcher.real_quick_ratio() < threshold:
        return 0.0
    if threshold and matcher.quick_ratio() < threshold:
        return 0.0
    return matcher.ratio()


def _meaningful_tokens(title: str) -> set[str]:
    return {
        token
        for token in title.split()
        if len(token) > 1 and token not in STOP_WORDS
    }
