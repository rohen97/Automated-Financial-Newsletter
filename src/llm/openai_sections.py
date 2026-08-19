from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from src.fetchers.provider_audit import record_error, record_openai_used


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def _source_brief(data: dict, sections: dict | None = None) -> dict[str, Any]:
    articles = data.get("ranked_articles", [])[:12]
    macro = data.get("macro", [])[:5]
    selected_story = (sections or {}).get("story_of_the_week", {})
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
        "selected_story": {
            "title": selected_story.get("title"),
            "narrative": selected_story.get("narrative"),
            "source": (selected_story.get("sources") or [{}])[0],
            "selection_signal": selected_story.get("selection_signal", {}),
        },
        "editorial_topic_signals": [
            {
                "phrase": row.get("phrase"),
                "status": row.get("status"),
                "article_count": row.get("article_count"),
                "source_count": row.get("source_count"),
            }
            for row in data.get("narrative_monitor", {}).get("rows", [])[:5]
        ],
    }


def enhance_sections_with_openai(sections: dict, data: dict) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return sections
    prompt = (
        "You write concise institutional market newsletter copy. "
        "Use only the supplied source brief. Return strict JSON with keys: "
        "executive_bullets, story_title, story_narrative, story_implications. "
        "Keep the feature centered on selected_story; editorial_topic_signals are supporting context, not standalone claims. "
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
                    {"role": "user", "content": json.dumps(_source_brief(data, sections), default=str)},
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
        generated_title = str(generated.get("story_title") or "")
        generated_narrative = str(generated.get("story_narrative") or "")
        if _story_topic_aligned(str(story.get("title", "")), generated_title):
            selected_copy = f"{story.get('title', '')} {story.get('narrative', '')}"
            if generated_narrative and _story_copy_aligned(selected_copy, generated_narrative):
                story["narrative"] = generated_narrative
            implications = generated.get("story_implications")
            if isinstance(implications, list) and implications:
                aligned_implications = [
                    str(item)
                    for item in implications[:4]
                    if _story_copy_aligned(selected_copy, str(item))
                ]
                if aligned_implications:
                    story["implications"] = aligned_implications
            story["openai_rewrite_status"] = "accepted"
        else:
            story["openai_rewrite_status"] = "rejected_topic_drift"
        sections["story_of_the_week"] = story
    except Exception as exc:
        record_error("openai", str(exc))
    return sections


def _story_topic_aligned(selected_title: str, generated_title: str) -> bool:
    selected = _topic_terms(selected_title)
    generated = _topic_terms(generated_title)
    if not selected or not generated:
        return False
    required = 1 if len(selected) <= 3 else 2
    return len(selected & generated) >= required


def _story_copy_aligned(selected_copy: str, generated_copy: str) -> bool:
    selected = _topic_terms(selected_copy)
    generated = _topic_terms(generated_copy)
    return bool(selected and generated and selected & generated)


def _topic_terms(value: str) -> set[str]:
    stopwords = {
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
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.casefold())
        if len(token) >= 4 and token not in stopwords
    }
