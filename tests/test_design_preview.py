from pathlib import Path

from src.main import build_newsletter
from src.render.assemble_newsletter import render_newsletter_html


def test_email_template_renders_brand_and_tables():
    newsletter = build_newsletter()
    html = render_newsletter_html(newsletter)
    assert "Wolf Research" in html
    assert "The week in one view" in html
    assert "MACRO PULSE" in html
    assert "Market tape" in html
    assert "FX Markets" in html
    assert "Commodities" in html
    assert "Chart of the Week" in html
    assert "What Changed This Week" in html
    assert "Dislocation Watch" in html
    assert "Narrative Monitor" not in html
    assert "Fixed Income Monitor" not in html
    assert "Story of the Week" in html
    assert html.count("Sector Scoreboard") == 1
    assert "heat-negative" in html
    assert 'name="color-scheme" content="light dark"' in html
    assert "@media (prefers-color-scheme: dark)" in html
    assert 'class="market-stack"' in html
    assert "border-left:1px solid #e6e1d8" in html
    assert Path("templates/newsletter.html.j2").exists()
