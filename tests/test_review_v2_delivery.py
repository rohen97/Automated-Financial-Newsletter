from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.send_review_v2 import _recipients, _subject, _validate_delivery
from src.emailer.send_email import EmailSafetyError


def test_subject_uses_newsletter_date_and_title():
    newsletter = {
        "title": "Weekly Market Brief",
        "generated_at": datetime(2026, 8, 17, 1, 0, tzinfo=UTC).isoformat(),
        "timezone": "Asia/Singapore",
    }

    assert _subject(newsletter) == "Wolf Research | Weekly Market Brief | 17 August 2026"


def test_recipient_parser_accepts_commas_and_semicolons():
    assert _recipients("a@example.com; b@example.com,c@example.com") == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
    ]


def test_delivery_blocks_failed_validation(tmp_path: Path):
    newsletter = {"warnings": [], "sections": {"chart_of_the_week": {}}}
    audit = {"validation_status": "blocked: fallback active", "fallback_source_count": 1}

    with pytest.raises(EmailSafetyError, match="delivery blocked"):
        _validate_delivery(newsletter, audit, tmp_path / "missing.html", tmp_path / "missing.png")
