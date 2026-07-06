# Wolf Research

Wolf Research is a Python content engine for an automated weekly financial newsletter for an investment office in Singapore. It builds an institutional, concise, source-backed newsletter covering macro, FX, commodities, private markets, sector leadership, headlines, a story of the week, and a forward watchlist.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Environment Variables

- `SEND_MODE=dry_run` saves outputs without sending email.
- `SEND_MODE=send` sends through SendGrid after safety checks pass.
- `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, and `NEWSLETTER_TO` are required for production email.
- `FRED_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `MARKETAUX_API_KEY`, and `CRUNCHBASE_API_KEY` are optional data integrations.
- `TIMEZONE=Asia/Singapore` keeps the newsletter aligned to Singapore time.

## Run Locally

```powershell
python -m src.main
```

Outputs are written to `output/latest/` and `output/archive/YYYY-MM-DD/`.

## Dry Run

Dry run is the default. It generates all outputs and never sends email:

```powershell
$env:SEND_MODE="dry_run"
python -m src.main
```

## Production Send

```powershell
$env:SEND_MODE="send"
python -m src.main
```

The send step is blocked if required sections are missing, fewer than five source URLs are present, schema validation fails, or generated text contains failure phrases such as `as an AI` or `I could not`.

## Add Sources

Edit `config/sources.yaml` to add RSS feeds, source quality scores, or fallback sources. Every article should include title, source, date, URL, summary, and category.

## Update Sections

Edit `config/newsletter.yaml` for required sections and newsletter settings. Section prompts live in `src/llm/prompts.py`; structured schemas live in `src/llm/schemas.py`.

## GitHub Actions

- `ci.yml` runs tests on push and pull request.
- `weekly_newsletter.yml` runs every Monday at `01:00 UTC`, equal to `09:00 Singapore time`, generates the newsletter, and uploads outputs as artifacts.

## Risk And Compliance Notes

This engine is for internal analytical distribution. It should not produce unsupported investment recommendations. Every factual claim should be traceable to a source URL or configured data source. Live API integrations should be reviewed before production use.
