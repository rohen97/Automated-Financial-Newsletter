from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from src.fetchers.provider_audit import record_error, record_gmail_messages
from src.processing.article_enrichment import enrich_article
from src.processing.clean import clean_text
from src.utils.dates import parse_date
from src.utils.io import project_path


UNTRUSTED_INSTRUCTION_PATTERNS = (
    r"ignore (all|any|the|your)?\s*(previous|prior) instructions",
    r"reveal (the )?(system|developer) prompt",
    r"call (this |a )?tool",
    r"send (an |this )?email",
    r"<script\b",
    r"javascript:",
)


def load_gmail_digest(config: dict, now: datetime | None = None) -> list[dict]:
    gmail_config = config.get("gmail_mcp") or {}
    if not gmail_config.get("enabled", False):
        return []

    digest_path = _resolve_path(gmail_config.get("digest_path", "data/inbox/gmail_digest.json"))
    if not digest_path.exists():
        return []

    try:
        payload = json.loads(digest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        record_error("gmail_mcp", f"Unable to read normalized digest: {exc}")
        return []

    generated_at = parse_date(payload.get("generated_at"))
    current = now or datetime.now(timezone.utc)
    max_age = timedelta(hours=int(gmail_config.get("max_age_hours", 192)))
    if not generated_at or current.astimezone(timezone.utc) - generated_at.astimezone(timezone.utc) > max_age:
        record_error("gmail_mcp", "Normalized Gmail digest is missing a valid timestamp or is stale")
        return []

    articles = []
    for item in payload.get("messages", [])[: int(gmail_config.get("max_messages", 60))]:
        article = _normalize_message(item)
        if article:
            articles.append(enrich_article(article))
    record_gmail_messages(len(articles))
    return articles


def _normalize_message(item: dict) -> dict | None:
    title = clean_text(item.get("subject") or item.get("title"))[:240]
    summary = clean_text(item.get("summary"))[:1000]
    url = clean_text(item.get("url"))
    if not title or not _is_http_url(url):
        return None
    if _contains_untrusted_instruction(f"{title} {summary}"):
        record_error("gmail_mcp", f"Rejected potentially unsafe newsletter item: {title[:80]}")
        return None

    published_at = parse_date(item.get("published_at") or item.get("date"))
    return {
        "title": title,
        "source": clean_text(item.get("source") or item.get("sender") or "Gmail newsletter")[:120],
        "published_at": published_at,
        "date": published_at.date().isoformat() if published_at else "",
        "url": url,
        "summary": summary,
        "category": clean_text(item.get("category") or "markets")[:60],
        "region": clean_text(item.get("region") or "")[:30],
        "source_type": "gmail_mcp",
        "gmail_message_id": clean_text(item.get("message_id"))[:120],
    }


def _contains_untrusted_instruction(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in UNTRUSTED_INSTRUCTION_PATTERNS)


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_path(*path.parts)
