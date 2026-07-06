from __future__ import annotations

from datetime import datetime

from src.llm.schemas import Newsletter


def assemble_newsletter(title: str, timezone: str, sections: dict, warnings: list[str] | None = None) -> Newsletter:
    return Newsletter(
        title=title,
        generated_at=datetime.now().astimezone(),
        timezone=timezone,
        sections=sections,
        warnings=warnings or [],
    )


def newsletter_to_markdown(newsletter: Newsletter) -> str:
    data = newsletter.model_dump(mode="json")
    lines = [f"# {data['title']}", "", f"Generated: {data['generated_at']}", ""]
    for key, section in data["sections"].items():
        lines.extend([f"## {section_title(key)}", ""])
        if isinstance(section, dict) and "bullets" in section:
            lines.extend(f"- {bullet}" for bullet in section.get("bullets", []))
        elif isinstance(section, dict) and "rows" in section:
            lines.append("| Asset | Last | 1W | 1M | Driver |")
            lines.append("|---|---:|---:|---:|---|")
            for row in section["rows"]:
                lines.append(f"| {row['label']} | {row['last']} | {row['one_week_change']} | {row['one_month_change']} | {row['driver']} |")
        elif isinstance(section, dict) and "narrative" in section:
            lines.append(section["narrative"])
            lines.extend(f"- {item}" for item in section.get("implications", []))
        elif isinstance(section, list):
            for item in section:
                title = item.get("title") or item.get("event")
                detail = item.get("why_it_matters", "")
                lines.append(f"- {title}" + (f": {detail}" if detail else ""))
        lines.append("")
    if data.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in data["warnings"])
    return "\n".join(lines).strip() + "\n"


def newsletter_to_html(newsletter: Newsletter) -> str:
    markdown = newsletter_to_markdown(newsletter)
    body = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body = body.replace("\n", "<br>\n")
    return f"<!doctype html><html><body style='font-family:Arial,sans-serif;line-height:1.5'>{body}</body></html>"


def section_title(key: str) -> str:
    return key.replace("_", " ").title()
