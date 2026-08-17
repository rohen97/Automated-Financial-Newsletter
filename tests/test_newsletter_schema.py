from datetime import datetime

from src.llm.schemas import Newsletter, NewsletterSection


def test_newsletter_schema_accepts_required_shape():
    newsletter = Newsletter(
        title="Weekly Market Brief",
        generated_at=datetime.now(),
        timezone="Asia/Singapore",
        sections={
            "executive_snapshot": NewsletterSection(
                title="Executive Snapshot",
                bullets=["Institutional summary"],
                sources=[{"name": "Sample Data", "url": "https://example.com/source"}],
            )
        },
    )
    assert newsletter.title == "Weekly Market Brief"
