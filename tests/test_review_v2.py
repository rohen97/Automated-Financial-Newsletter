from pathlib import Path

from src.llm.schemas import Newsletter
from src.render.assemble_newsletter import render_newsletter_html
from src.render.review_v2 import render_review_v2_html


def test_review_v2_is_a_shorter_separate_editorial_variant():
    latest_json = Path("output/latest/newsletter.json")
    newsletter = Newsletter.model_validate_json(latest_json.read_text(encoding="utf-8"))

    initial_html = render_newsletter_html(newsletter)
    review_html = render_review_v2_html(newsletter)

    assert "Three things that matter" in review_html
    assert review_html.count('class="signal-index"') == 3
    assert "MARKET IMPACT /" in review_html
    assert "Markets at a glance" in review_html
    assert "Sector leadership" in review_html
    assert "Portfolio impact" in review_html
    assert "Week ahead" in review_html
    assert "One headline per region" in review_html
    assert "Largest monitored holdings" not in review_html
    assert "Sector Scoreboard" not in review_html
    assert "Private markets and portfolio intelligence" not in review_html
    assert "debt s</p>" not in review_html
    assert "YTD: the +5.</p>" not in review_html
    assert 'class="sector-metrics"' in review_html
    assert "color:#167451" in review_html
    assert "color:#a23b36" in review_html
    assert 'name="color-scheme" content="light dark"' in review_html
    assert "@media (prefers-color-scheme: dark)" in review_html
    assert "@media print" in review_html
    assert "background: #fcfbf8 !important" in review_html
    assert "font-family: Arial, Helvetica, sans-serif" in review_html
    assert "Selection score:" not in review_html
    assert "requests comment on a proposal" not in review_html
    assert "COMAC challenge the aviation" not in review_html
    assert len(review_html) < len(initial_html)
