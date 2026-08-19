from pathlib import Path

from src.llm.schemas import Newsletter
from src.render.assemble_newsletter import render_newsletter_html
from src.render.review_v2 import _global_scan, _story_view, render_review_v2_html


def test_review_v2_is_a_shorter_separate_editorial_variant():
    latest_json = Path("output/latest/newsletter.json")
    newsletter = Newsletter.model_validate_json(latest_json.read_text(encoding="utf-8"))

    initial_html = render_newsletter_html(newsletter)
    review_html = render_review_v2_html(newsletter)

    assert "Three things that matter" in review_html
    assert "WEEKLY EDITION" in review_html
    assert "V2 REVIEW" not in review_html
    assert review_html.count('class="signal-index"') == 3
    assert "MARKET IMPACT /" in review_html
    assert "Markets at a glance" in review_html
    assert "What Changed This Week" in review_html
    assert "Dislocation Watch" in review_html
    assert "Narrative Monitor" not in review_html
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


def test_global_scan_keeps_material_headlines_and_rejects_administrative_notices():
    regions = [
        {
            "region": "US",
            "headlines": [
                {
                    "headline": "Federal Reserve requests comment on a proposal",
                    "source": "Federal Reserve",
                    "category": "Macro",
                    "url": "https://example.test/fed-notice",
                }
            ],
        },
        {
            "region": "EU",
            "headlines": [
                {
                    "headline": "The rise in defence spending and the euro area economy",
                    "source": "European Central Bank",
                    "category": "Macro",
                    "url": "https://example.test/ecb",
                }
            ],
        },
        {
            "region": "EMEA",
            "headlines": [
                {
                    "headline": "Libya seeks investment to develop oil resources",
                    "source": "Financial Times",
                    "category": "Equities",
                    "url": "https://example.test/libya",
                }
            ],
        },
        {
            "region": "Global",
            "headlines": [
                {
                    "headline": "Africa's public debt amid global headwinds",
                    "source": "Bank for International Settlements",
                    "category": "Macro",
                    "url": "https://example.test/feature-duplicate",
                },
                {
                    "headline": "AI and monetary policy",
                    "source": "Bank for International Settlements",
                    "category": "Macro",
                    "url": "https://example.test/bis",
                }
            ],
        },
    ]

    scan = {
        item["region"]: item
        for item in _global_scan(regions, feature_title="Africa's public debt amid global headwinds")
    }

    assert scan["US"]["url"] == ""
    assert scan["EU"]["url"] == "https://example.test/ecb"
    assert scan["EMEA"]["url"] == "https://example.test/libya"
    assert scan["Global"]["url"] == "https://example.test/bis"


def test_story_view_does_not_attach_an_unrelated_first_watch_item():
    story = {
        "title": "The cooperative spirit at the heart of the digital euro",
        "narrative": "An ECB lecture on the digital euro project.",
        "implications": ["The digital euro matters for European payments infrastructure."],
        "sources": [],
    }
    rows = [
        {
            "event": "Inflation and Fed communication",
            "portfolio_relevance": "Impacts USD, duration, and US growth equities",
        }
    ]

    view = _story_view(story, rows)

    assert view["watch"].startswith("Further ECB digital-euro guidance")
    assert "Fed communication" not in view["watch"]
