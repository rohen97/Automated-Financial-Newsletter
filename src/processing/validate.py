from __future__ import annotations

from collections.abc import Iterable

BLOCKED_PHRASES = ("as an ai", "i could not", "i cannot browse", "unsupported recommendation")


def collect_source_urls(newsletter: dict) -> set[str]:
    urls: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            url = value.get("url")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                urls.add(url)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(newsletter)
    return urls


def validate_required_sections(newsletter: dict, required_sections: Iterable[str]) -> list[str]:
    sections = newsletter.get("sections", {})
    missing = [section for section in required_sections if section not in sections or not sections[section]]
    return missing


def validate_source_urls(newsletter: dict, minimum_sources: int = 5) -> list[str]:
    urls = collect_source_urls(newsletter)
    if len(urls) < minimum_sources:
        return [f"Newsletter has {len(urls)} source URLs; minimum is {minimum_sources}."]
    return []


def validate_blocked_phrases(text: str) -> list[str]:
    lowered = text.lower()
    return [phrase for phrase in BLOCKED_PHRASES if phrase in lowered]


def run_quality_checks(newsletter: dict, required_sections: Iterable[str]) -> list[str]:
    warnings = []
    missing = validate_required_sections(newsletter, required_sections)
    if missing:
        warnings.append(f"Missing required sections: {', '.join(missing)}")
    warnings.extend(validate_source_urls(newsletter))
    blocked = validate_blocked_phrases(str(newsletter))
    if blocked:
        warnings.append(f"Blocked phrases found: {', '.join(blocked)}")
    return warnings
