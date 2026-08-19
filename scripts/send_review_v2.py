from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.charts.chart_renderer import chart_metadata_matches, chart_metadata_path  # noqa: E402
from src.emailer.send_email import EmailSafetyError, send_email, validate_html_body  # noqa: E402
from src.utils.env import load_local_env  # noqa: E402


def main() -> None:
    load_local_env()
    newsletter_path = ROOT / "output" / "latest" / "newsletter.json"
    audit_path = ROOT / "output" / "latest" / "audit_log.json"
    html_path = ROOT / "output" / "review_v2" / "newsletter_v2.html"
    chart_path = ROOT / "output" / "latest" / "chart_of_the_week.png"

    newsletter = _read_json(newsletter_path)
    audit = _read_json(audit_path)
    _validate_delivery(newsletter, audit, html_path, chart_path)

    mode = os.getenv("SEND_MODE", "dry_run")
    if mode != "send":
        print(json.dumps({"sent": False, "mode": "dry_run", "reason": "SEND_MODE is not send"}))
        return

    recipients = _recipients(os.getenv("NEWSLETTER_TO", ""))
    if not recipients:
        raise EmailSafetyError("NEWSLETTER_TO is required for finalized V2 delivery.")
    bcc_recipients = _recipients(os.getenv("NEWSLETTER_BCC", ""))

    html = html_path.read_text(encoding="utf-8")
    result = send_email(
        _subject(newsletter),
        html,
        recipients,
        warnings=newsletter.get("warnings", []),
        bcc_recipients=bcc_recipients,
    )
    print(json.dumps(result))


def _validate_delivery(newsletter: dict, audit: dict, html_path: Path, chart_path: Path) -> None:
    problems = []
    if audit.get("validation_status") != "ok":
        problems.append(str(audit.get("validation_status") or "validation status missing"))
    if audit.get("fallback_source_count", 0) and os.getenv("ALLOW_FALLBACK_IN_SEND", "false").lower() != "true":
        problems.append("fallback sources are present")
    if newsletter.get("warnings"):
        problems.append("newsletter warnings are present")
    if not html_path.exists():
        problems.append("finalized V2 HTML is missing")
    else:
        try:
            validate_html_body(html_path.read_text(encoding="utf-8"))
        except EmailSafetyError as exc:
            problems.append(str(exc))
    if not chart_path.exists():
        problems.append("chart image is missing")
    else:
        metadata_file = chart_metadata_path(chart_path)
        metadata = _read_json(metadata_file) if metadata_file.exists() else {}
        chart = newsletter.get("sections", {}).get("chart_of_the_week", {})
        if not chart_metadata_matches(chart, metadata):
            problems.append("chart image metadata does not match newsletter.json")
    if problems:
        raise EmailSafetyError("Finalized V2 delivery blocked: " + "; ".join(problems))


def _subject(newsletter: dict) -> str:
    timezone = newsletter.get("timezone", "Asia/Singapore")
    generated = datetime.fromisoformat(str(newsletter["generated_at"])).astimezone(ZoneInfo(timezone))
    return f"Wolf Research | {newsletter['title']} | {generated.day} {generated.strftime('%B %Y')}"


def _recipients(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise EmailSafetyError(f"Required delivery file is missing: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
