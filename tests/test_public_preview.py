from pathlib import Path

from src.llm.schemas import Newsletter
from src.render.assemble_newsletter import render_newsletter_html


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "public_preview_newsletter.json"


def test_public_preview_is_synthetic_and_portfolio_safe():
    newsletter = Newsletter.model_validate_json(FIXTURE.read_text(encoding="utf-8"))
    html = render_newsletter_html(newsletter)

    assert "Public Design Sample" in html
    assert "Portfolio Snapshot" not in html
    assert "Illustrative" in html
    for sensitive_name in (
        "Meta Wolf",
        "Softtech Engineers",
        "Bayerische Motoren Werke",
        "Singapore Airlines",
        "CapitaLand",
    ):
        assert sensitive_name not in html


def test_pages_workflow_uses_public_fixture():
    workflow = (ROOT / ".github/workflows/pages_preview.yml").read_text(encoding="utf-8")

    assert "--input examples/public_preview_newsletter.json" in workflow
    assert "--source output/public_design_preview/newsletter_preview.html" in workflow
