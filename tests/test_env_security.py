from pathlib import Path


SECRET_KEYS = {
    "OPENAI_API_KEY",
    "FRED_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
    "MARKETAUX_API_KEY",
    "FT_API_KEY",
    "TIINGO_API_KEY",
    "SENDGRID_API_KEY",
    "GMAIL_APP_PASSWORD",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
    "NEWSLETTER_BCC",
}

EXPECTED_EXAMPLE = """OPENAI_API_KEY=
FRED_API_KEY=
ALPHA_VANTAGE_API_KEY=
MARKETAUX_API_KEY=
FT_API_KEY=
FT_API_ORG_NAME=WolfResearch
FT_API_TRACKING_SOURCE=email
TIINGO_API_KEY=
TIINGO_NEWS_ENABLED=false
TIINGO_ALLOW_PERSISTENCE=false
TIINGO_LICENSE_MODE=internal

SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=
NEWSLETTER_TO=
NEWSLETTER_BCC=
EMAIL_PROVIDER=gmail_api
GMAIL_FROM_EMAIL=
GMAIL_CLIENT_ID=
GMAIL_CLIENT_SECRET=
GMAIL_REFRESH_TOKEN=
GMAIL_APP_PASSWORD=

SEND_MODE=dry_run
TIMEZONE=Asia/Singapore
ALLOW_FALLBACK_IN_SEND=false
ALLOW_COMPANY_SEND=false
MAX_COMPANY_RECIPIENTS=500

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
    assert "client_secret*.json" in text


def test_weekly_workflow_reads_api_keys_from_secrets():
    workflow = Path(".github/workflows/weekly_newsletter.yml").read_text(encoding="utf-8")
    for key in (
        "OPENAI_API_KEY",
        "FRED_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "MARKETAUX_API_KEY",
        "FT_API_KEY",
        "TIINGO_API_KEY",
        "GMAIL_FROM_EMAIL",
        "GMAIL_CLIENT_ID",
        "GMAIL_CLIENT_SECRET",
        "GMAIL_REFRESH_TOKEN",
        "GMAIL_APP_PASSWORD",
        "NEWSLETTER_TO",
        "NEWSLETTER_BCC",
    ):
        assert f"{key}: ${{{{ secrets.{key} }}}}" in workflow
