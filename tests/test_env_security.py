from pathlib import Path


SECRET_KEYS = {
    "OPENAI_API_KEY",
    "FRED_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "MARKETAUX_API_KEY",
    "SENDGRID_API_KEY",
}

EXPECTED_EXAMPLE = """OPENAI_API_KEY=
FRED_API_KEY=
ALPHA_VANTAGE_API_KEY=
MARKETAUX_API_KEY=

SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
NEWSLETTER_TO=

SEND_MODE=dry_run
TIMEZONE=Asia/Singapore
ALLOW_FALLBACK_IN_SEND=false

MARKET_DATA_PROVIDER=alpha_vantage
MACRO_DATA_PROVIDER=fred
NEWS_PROVIDER=marketaux
LLM_PROVIDER=openai
"""


def test_env_example_contains_placeholders_only():
    text = Path(".env.example").read_text(encoding="utf-8")
    assert text == EXPECTED_EXAMPLE
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in SECRET_KEYS:
            assert value == ""


def test_env_files_are_ignored():
    text = Path(".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in text
    assert ".env.local" in text
    assert "*.key" in text


def test_weekly_workflow_reads_api_keys_from_secrets():
    workflow = Path(".github/workflows/weekly_newsletter.yml").read_text(encoding="utf-8")
    for key in ("OPENAI_API_KEY", "FRED_API_KEY", "ALPHA_VANTAGE_API_KEY", "MARKETAUX_API_KEY"):
        assert f"{key}: ${{{{ secrets.{key} }}}}" in workflow
