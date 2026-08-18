from __future__ import annotations

import base64
from email.message import EmailMessage
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import smtplib
import ssl

import requests


class EmailSafetyError(RuntimeError):
    pass


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIN_HTML_BYTES = 1024


def send_email(subject: str, html: str, recipients: list[str], warnings: list[str] | None = None) -> dict:
    send_mode = os.getenv("SEND_MODE", "dry_run")
    if send_mode != "send":
        return {"sent": False, "mode": "dry_run", "reason": "SEND_MODE is not send"}
    if warnings:
        raise EmailSafetyError("; ".join(warnings))
    validate_html_body(html)
    if not recipients:
        raise EmailSafetyError("At least one email recipient is required for send mode.")

    chart_path = PROJECT_ROOT / "output" / "latest" / "chart_of_the_week.png"
    if chart_path.exists():
        html = html.replace('src="chart_of_the_week.png"', 'src="cid:chart_of_the_week"')
        html = html.replace("src='chart_of_the_week.png'", "src='cid:chart_of_the_week'")
    plain_text = html_to_text(html)

    provider = os.getenv("EMAIL_PROVIDER", "sendgrid").strip().lower()
    if provider in {"gmail_api", "gmail_oauth"}:
        return _send_gmail_api(
            subject=subject,
            html=html,
            plain_text=plain_text,
            recipients=recipients,
            chart_path=chart_path,
        )
    if provider in {"gmail", "gmail_smtp"}:
        return _send_gmail_smtp(
            subject=subject,
            html=html,
            plain_text=plain_text,
            recipients=recipients,
            chart_path=chart_path,
        )
    if provider == "sendgrid":
        return _send_sendgrid(
            subject=subject,
            html=html,
            plain_text=plain_text,
            recipients=recipients,
            chart_path=chart_path,
        )
    raise EmailSafetyError(
        f"Unsupported EMAIL_PROVIDER '{provider}'. Use gmail_api, gmail_smtp, or "
        "sendgrid."
    )


def _send_sendgrid(
    *,
    subject: str,
    html: str,
    plain_text: str,
    recipients: list[str],
    chart_path: Path,
) -> dict:
    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("SENDGRID_FROM_EMAIL")
    if not api_key or not from_email:
        raise EmailSafetyError("SendGrid credentials are required for send mode.")
    attachments = []
    if chart_path.exists():
        attachments.append(_inline_attachment(chart_path, "chart_of_the_week"))
    payload = {
        "personalizations": [{"to": [{"email": email} for email in recipients]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": plain_text},
            {"type": "text/html", "value": html},
        ],
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
    return {
        "sent": True,
        "mode": "send",
        "provider": "sendgrid",
        "status_code": response.status_code,
        "html_bytes": len(html.encode("utf-8")),
        "plain_text_bytes": len(plain_text.encode("utf-8")),
        "inline_attachment_count": len(attachments),
    }


def _send_gmail_smtp(
    *,
    subject: str,
    html: str,
    plain_text: str,
    recipients: list[str],
    chart_path: Path,
) -> dict:
    from_email = os.getenv("GMAIL_FROM_EMAIL")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not from_email or not app_password:
        raise EmailSafetyError(
            "Gmail SMTP credentials are required for send mode. Set "
            "GMAIL_FROM_EMAIL and GMAIL_APP_PASSWORD."
        )

    message, inline_attachment_count = _build_mime_message(
        subject=subject,
        from_email=from_email,
        html=html,
        plain_text=plain_text,
        recipients=recipients,
        chart_path=chart_path,
    )

    try:
        port = int(os.getenv("GMAIL_SMTP_PORT", "465"))
    except ValueError as exc:
        raise EmailSafetyError("GMAIL_SMTP_PORT must be a valid integer.") from exc
    host = os.getenv("GMAIL_SMTP_HOST", "smtp.gmail.com")
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as smtp:
        smtp.login(from_email, app_password)
        smtp.send_message(message)

    return {
        "sent": True,
        "mode": "send",
        "provider": "gmail_smtp",
        "html_bytes": len(html.encode("utf-8")),
        "plain_text_bytes": len(plain_text.encode("utf-8")),
        "inline_attachment_count": inline_attachment_count,
    }


def _send_gmail_api(
    *,
    subject: str,
    html: str,
    plain_text: str,
    recipients: list[str],
    chart_path: Path,
) -> dict:
    credentials = {
        "client_id": os.getenv("GMAIL_CLIENT_ID"),
        "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
        "refresh_token": os.getenv("GMAIL_REFRESH_TOKEN"),
        "from_email": os.getenv("GMAIL_FROM_EMAIL"),
    }
    missing = [name for name, value in credentials.items() if not value]
    if missing:
        raise EmailSafetyError(
            "Gmail API OAuth credentials are required for send mode. Missing: "
            + ", ".join(missing)
            + "."
        )

    try:
        token_response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": credentials["client_id"],
                "client_secret": credentials["client_secret"],
                "refresh_token": credentials["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=20,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
    except (requests.RequestException, ValueError) as exc:
        raise EmailSafetyError("Gmail OAuth token refresh failed.") from exc
    if not access_token:
        raise EmailSafetyError("Gmail OAuth token refresh returned no access token.")

    message, inline_attachment_count = _build_mime_message(
        subject=subject,
        from_email=str(credentials["from_email"]),
        html=html,
        plain_text=plain_text,
        recipients=recipients,
        chart_path=chart_path,
    )
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    try:
        send_response = requests.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"raw": encoded_message},
            timeout=30,
        )
        send_response.raise_for_status()
        response_payload = send_response.json()
    except (requests.RequestException, ValueError) as exc:
        raise EmailSafetyError("Gmail API message delivery failed.") from exc

    return {
        "sent": True,
        "mode": "send",
        "provider": "gmail_api",
        "status_code": send_response.status_code,
        "message_id": response_payload.get("id"),
        "html_bytes": len(html.encode("utf-8")),
        "plain_text_bytes": len(plain_text.encode("utf-8")),
        "inline_attachment_count": inline_attachment_count,
    }


def _build_mime_message(
    *,
    subject: str,
    from_email: str,
    html: str,
    plain_text: str,
    recipients: list[str],
    chart_path: Path,
) -> tuple[EmailMessage, int]:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = from_email
    message["To"] = ", ".join(recipients)
    message.set_content(plain_text)
    message.add_alternative(html, subtype="html")

    inline_attachment_count = 0
    if chart_path.exists():
        html_part = message.get_payload()[-1]
        html_part.add_related(
            chart_path.read_bytes(),
            maintype="image",
            subtype="png",
            cid="<chart_of_the_week>",
            filename=chart_path.name,
            disposition="inline",
        )
        inline_attachment_count = 1
    return message, inline_attachment_count


def validate_html_body(html: str) -> None:
    encoded_size = len(html.encode("utf-8")) if isinstance(html, str) else 0
    if encoded_size < MIN_HTML_BYTES:
        raise EmailSafetyError(
            f"Email HTML is empty or unexpectedly short ({encoded_size} bytes)."
        )
    lowered = html.lower()
    required_markers = ("<html", "<body", "</body>", "</html>")
    missing = [marker for marker in required_markers if marker not in lowered]
    if missing:
        raise EmailSafetyError(
            "Email HTML is incomplete; missing " + ", ".join(missing) + "."
        )
    if len(html_to_text(html)) < 200:
        raise EmailSafetyError("Email HTML does not contain enough readable content.")


def html_to_text(html: str) -> str:
    parser = _EmailTextExtractor()
    parser.feed(html)
    parser.close()
    lines = [re.sub(r"\s+", " ", line).strip() for line in parser.lines]
    return "\n".join(line for line in lines if line)


class _EmailTextExtractor(HTMLParser):
    _ignored_tags = {"head", "style", "script"}
    _block_tags = {
        "br",
        "body",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "p",
        "section",
        "td",
        "th",
        "tr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buffer: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._ignored_tags:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in self._block_tags:
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if tag in self._ignored_tags:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif not self._ignored_depth and tag in self._block_tags:
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        if self._buffer:
            self.lines.append(" ".join(self._buffer))
            self._buffer.clear()


def _inline_attachment(path: Path, content_id: str) -> dict:
    return {
        "content": base64.b64encode(path.read_bytes()).decode("ascii"),
        "type": "image/png",
        "filename": path.name,
        "disposition": "inline",
        "content_id": content_id,
    }
