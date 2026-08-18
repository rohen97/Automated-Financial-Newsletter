from __future__ import annotations

import pytest

from src.emailer import send_email as emailer


def _complete_html() -> str:
    body = "Wolf Research market brief content. " * 80
    return f"<!doctype html><html><head><title>Brief</title></head><body>{body}</body></html>"


def test_validate_html_body_rejects_empty_or_incomplete_content():
    with pytest.raises(emailer.EmailSafetyError, match="unexpectedly short"):
        emailer.validate_html_body("")

    incomplete = "<html><body>" + ("market content " * 100)
    with pytest.raises(emailer.EmailSafetyError, match="incomplete"):
        emailer.validate_html_body(incomplete)


def test_send_email_includes_plain_text_and_html(monkeypatch):
    captured: dict = {}

    class Response:
        status_code = 202

        @staticmethod
        def raise_for_status() -> None:
            return None

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "payload": json, "timeout": timeout})
        return Response()

    monkeypatch.setenv("SEND_MODE", "send")
    monkeypatch.setenv("EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setenv("SENDGRID_API_KEY", "test-api-key")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "sender@example.com")
    monkeypatch.setattr(emailer.requests, "post", fake_post)
    monkeypatch.setattr(emailer, "PROJECT_ROOT", emailer.Path("missing-project-root"))

    result = emailer.send_email(
        "Wolf Research test",
        _complete_html(),
        ["reader@example.com"],
    )

    assert result["sent"] is True
    assert result["html_bytes"] > 1024
    assert result["plain_text_bytes"] > 200
    assert captured["payload"]["content"][0]["type"] == "text/plain"
    assert "Wolf Research market brief content" in captured["payload"]["content"][0]["value"]
    assert captured["payload"]["content"][1]["type"] == "text/html"


def test_send_email_via_gmail_smtp_includes_both_bodies_and_inline_chart(
    monkeypatch, tmp_path
):
    captured: dict = {}

    class FakeSMTP:
        def __init__(self, host, port, *, context, timeout):
            captured.update(
                {"host": host, "port": port, "context": context, "timeout": timeout}
            )

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def login(self, email, password):
            captured["login"] = (email, password)

        def send_message(self, message):
            captured["message"] = message

    chart_path = tmp_path / "output" / "latest" / "chart_of_the_week.png"
    chart_path.parent.mkdir(parents=True)
    chart_path.write_bytes(b"\x89PNG\r\n\x1a\nchart-data")
    html = _complete_html().replace(
        "<body>", '<body><img src="chart_of_the_week.png" alt="Chart of the week">'
    )

    monkeypatch.setenv("SEND_MODE", "send")
    monkeypatch.setenv("EMAIL_PROVIDER", "gmail_smtp")
    monkeypatch.setenv("GMAIL_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "test-app-password")
    monkeypatch.setattr(emailer.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(emailer, "PROJECT_ROOT", tmp_path)

    result = emailer.send_email(
        "Wolf Research Gmail test",
        html,
        ["reader@example.com"],
    )

    message = captured["message"]
    content_types = [part.get_content_type() for part in message.walk()]
    assert result["sent"] is True
    assert result["provider"] == "gmail_smtp"
    assert result["inline_attachment_count"] == 1
    assert captured["host"] == "smtp.gmail.com"
    assert captured["port"] == 465
    assert captured["login"] == ("sender@example.com", "test-app-password")
    assert "text/plain" in content_types
    assert "text/html" in content_types
    assert "image/png" in content_types
    html_part = next(
        part for part in message.walk() if part.get_content_type() == "text/html"
    )
    image_part = next(
        part for part in message.walk() if part.get_content_type() == "image/png"
    )
    assert "cid:chart_of_the_week" in html_part.get_content()
    assert image_part["Content-ID"] == "<chart_of_the_week>"
    assert "test-app-password" not in message.as_string()


def test_gmail_smtp_requires_credentials(monkeypatch):
    monkeypatch.setenv("SEND_MODE", "send")
    monkeypatch.setenv("EMAIL_PROVIDER", "gmail_smtp")
    monkeypatch.delenv("GMAIL_FROM_EMAIL", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    monkeypatch.setattr(emailer, "PROJECT_ROOT", emailer.Path("missing-project-root"))

    with pytest.raises(emailer.EmailSafetyError, match="Gmail SMTP credentials"):
        emailer.send_email(
            "Wolf Research Gmail test",
            _complete_html(),
            ["reader@example.com"],
        )
