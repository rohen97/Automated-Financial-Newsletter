from pathlib import Path

from src.main import build_newsletter
from src.render.assemble_newsletter import render_newsletter_html


def test_email_template_renders_brand_and_tables():
    newsletter = build_newsletter()
    html = render_newsletter_html(newsletter)
    assert "Wolf Research" in html
    assert "FX Markets" in html
    assert "Commodities" in html
    assert "Story of the Week" in html
    assert html.count("Sector Scoreboard") == 1
    assert "heat-negative" in html
    assert Path("templates/newsletter.html.j2").exists()
