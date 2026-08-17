from __future__ import annotations

import base64
import os
from pathlib import Path

import requests


class EmailSafetyError(RuntimeError):
    pass


def send_email(subject: str, html: str, recipients: list[str], warnings: list[str] | None = None) -> dict:
    send_mode = os.getenv("SEND_MODE", "dry_run")
    if send_mode != "send":
        return {"sent": False, "mode": "dry_run", "reason": "SEND_MODE is not send"}
    if warnings:
        raise EmailSafetyError("; ".join(warnings))
    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("SENDGRID_FROM_EMAIL")
    if not api_key or not from_email or not recipients:
        raise EmailSafetyError("SendGrid credentials and recipients are required for send mode.")
    attachments = []
    chart_path = Path("output/latest/chart_of_the_week.png")
    if chart_path.exists():
        html = html.replace('src="chart_of_the_week.png"', 'src="cid:chart_of_the_week"')
        html = html.replace("src='chart_of_the_week.png'", "src='cid:chart_of_the_week'")
        attachments.append(_inline_attachment(chart_path, "chart_of_the_week"))
    payload = {
        "personalizations": [{"to": [{"email": email} for email in recipients]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }
    if attachments:
        payload["attachments"] = attachments
    response = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return {"sent": True, "mode": "send", "status_code": response.status_code}


def _inline_attachment(path: Path, content_id: str) -> dict:
    return {
        "content": base64.b64encode(path.read_bytes()).decode("ascii"),
        "type": "image/png",
        "filename": path.name,
        "disposition": "inline",
        "content_id": content_id,
    }
