from __future__ import annotations

import json
import os
from typing import Any

import requests

from src.fetchers.provider_audit import record_error, record_openai_used


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def _source_brief(data: dict) -> dict[str, Any]:
    articles = data.get("ranked_articles", [])[:12]
    macro = data.get("macro", [])[:5]
    return {
        "macro": [{"indicator": item.get("indicator"), "value": item.get("value"), "comment": item.get("comment")} for item in macro],
        "headlines": [
            {
                "title": item.get("title"),
                "source": item.get("source"),
                "category": item.get("category"),
                "summary": item.get("summary"),
            }
            for item in articles
        ],
        "portfolio": {
            "equity_kpis": data.get("equity_monitor", {}).get("kpis", []),
        },
        "chart_of_the_week": {
            "title": data.get("chart_of_the_week", {}).get("title"),
            "subtitle": data.get("chart_of_the_week", {}).get("subtitle"),
            "takeaway": data.get("chart_of_the_week", {}).get("takeaway"),
        },
    }


def enhance_sections_with_openai(sections: dict, data: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return sections
    prompt = (
        "You write concise institutional market newsletter copy. "
        "Use only the supplied source brief. Return strict JSON with keys: "
        "executive_bullets, story_title, story_narrative, story_implications. "
        "No investment advice, no first person, no 'as an AI', no inability language."
    )
    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                "input": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(_source_brief(data), default=str)},
                ],
                "text": {"format": {"type": "json_object"}},
                "max_output_tokens": 900,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload.get("output_text")
        if not text:
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"}:
                        text = content.get("text")
                        break
                if text:
                    break
        generated = json.loads(text or "{}")
        record_openai_used()
        bullets = generated.get("executive_bullets")
        if isinstance(bullets, list) and bullets:
            sections["executive_snapshot"]["bullets"] = [str(item) for item in bullets[:5]]
        story = sections.get("story_of_the_week", {})
        if generated.get("story_title"):
            story["title"] = str(generated["story_title"])
        if generated.get("story_narrative"):
            story["narrative"] = str(generated["story_narrative"])
        implications = generated.get("story_implications")
        if isinstance(implications, list) and implications:
            story["implications"] = [str(item) for item in implications[:4]]
        sections["story_of_the_week"] = story
    except Exception as exc:
        record_error("openai", str(exc))
    return sections
