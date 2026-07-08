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

## Real Content Mode

By default, the pipeline is deterministic and safe for tests. To pull live RSS/news feeds and live Yahoo Finance chart data where available:

```powershell
$env:LIVE_FETCH="true"
$env:LIVE_MARKET_DATA="true"
python -m src.main
```

Live mode still falls back gracefully when an API/feed is unavailable. Source URLs and warnings are written to:

```text
output/latest/source_audit.json
output/archive/YYYY-MM-DD/source_audit.json
```

## Portfolio-Aware Mode

The newsletter can rank headlines and frame commentary around current portfolio exposures. The default sample portfolio is:

```text
examples/current_portfolio.csv
```

The equity and issuer-only fixed income monitors use:

```text
data/portfolio/equity_holdings.csv
data/portfolio/fixed_income_holdings.csv
data/portfolio/portfolio_config.yaml
```

Expected columns:

```text
holding,asset_class,region,sector,currency,weight
```

Configure the input path and thresholds in:

```text
config/portfolio.yaml
```

When portfolio mode is enabled, the newsletter adds Portfolio Snapshot, Equity Holdings Monitor, Fixed Income Monitor, Portfolio-Linked News, Regional Headlines, and a portfolio-aware watchlist.

Manual pricing and issuer-only fixed income limitations are written to:

```text
output/latest/audit_log.json
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

## Email Design Preview

The institutional navy and gold HTML email template lives at `templates/newsletter.html.j2`, with email-safe CSS in `assets/newsletter.css`.

Generate a preview:

```powershell
python scripts/preview_design.py
```

The preview is saved to:

```text
output/design_preview/newsletter_preview.html
```

## GitHub Pages Preview

The `Pages Preview` workflow publishes a static sample preview to GitHub Pages. It deploys only rendered HTML from `public_preview/`; it does not publish `.env`, audit logs, JSON outputs, or raw secret files.

Expected URL after Pages is enabled:

```text
https://rohen97.github.io/wolf-research/
```

To run locally before deployment:

```powershell
python scripts/preview_design.py
python scripts/build_pages_preview.py
```

Enable Pages in GitHub with source set to `GitHub Actions`, then run the `Pages Preview` workflow manually for the first publish.

## GitHub Actions

- `ci.yml` runs tests on push and pull request.
- `weekly_newsletter.yml` runs every Monday at `01:00 UTC`, equal to `09:00 Singapore time`, generates the newsletter, and uploads outputs as artifacts.
- `pages_preview.yml` publishes the rendered preview to GitHub Pages.

## Risk And Compliance Notes

This engine is for internal analytical distribution. It should not produce unsupported investment recommendations. Every factual claim should be traceable to a source URL or configured data source. Live API integrations should be reviewed before production use.
