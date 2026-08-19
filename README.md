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
- `SEND_MODE=send` sends through the provider selected by `EMAIL_PROVIDER` after safety checks pass.
- `EMAIL_PROVIDER=gmail_api` uses `GMAIL_FROM_EMAIL`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, and `NEWSLETTER_TO`.
- `EMAIL_PROVIDER=gmail_smtp` remains available for accounts that support Google app passwords.
- `EMAIL_PROVIDER=sendgrid` uses `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, and `NEWSLETTER_TO`.
- `FRED_API_KEY`, `ALPHA_VANTAGE_API_KEY`, `MARKETAUX_API_KEY`, `FT_API_KEY`, `TIINGO_API_KEY`, and `CRUNCHBASE_API_KEY` are optional data integrations.
- `FT_API_ORG_NAME` and `FT_API_TRACKING_SOURCE` configure the campaign attribution required on FT article links.
- `TIMEZONE=Asia/Singapore` keeps the newsletter aligned to Singapore time.

## Run Locally

```powershell
python -m src.main
```

Outputs are written atomically to `output/latest/` and
`output/archive/YYYY-MM-DD/`. `output/latest/manifest.json` records checksums,
file sizes, provider status, validation status, and run duration for the edition.

The bounded-concurrency DAG, cache policy, memory model, and remaining trade-offs
are documented in
[`docs/architecture_performance_review.md`](docs/architecture_performance_review.md).
The complete content-to-email and GitHub Pages render flow is documented in
[`docs/design_pipeline.md`](docs/design_pipeline.md). Both documents include
GitHub-rendered Mermaid diagrams for review and handover.
Run the quota-safe mocked performance check with:

```powershell
python scripts/benchmark_pipeline.py
```

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

## Financial Times API

Set `FT_API_KEY` in the local `.env` file or as a GitHub Actions secret. The integration sends the key only in the
`X-Api-Key` header and requests title, lifecycle, location, and summary data from
`POST https://api.ft.com/content/search/v1`. It does not retrieve or republish full article bodies.

FT API access depends on the endpoints enabled by your FT licence. Configure the licensed organisation name through
`FT_API_ORG_NAME`; links include the required `FTCamp` attribution using `FT_API_TRACKING_SOURCE=email`. If the Search
API is unavailable for the key, the provider records the error without exposing the key and the existing FT RSS feed
remains available as a fallback.

The API contract and licence-specific requirements are documented in the
[FT API reference](https://developer.ft.com/portal/docs-api-reference) and
[FT datamining quick start](https://developer.ft.com/portal/docs-quick-start-guides-datamining-licence).

## Tiingo News API

Set `TIINGO_API_KEY` locally or as a GitHub Actions secret. Authentication is sent only through the
`Authorization: Token ...` header; the token is never placed in request URLs or audit logs. The provider uses the
official `GET https://api.tiingo.com/tiingo/news` endpoint, caps request and response sizes, normalizes original
publisher names and URLs, and retains Tiingo ticker and topic tags for newsletter relevance scoring.

Tiingo access is additive to Marketaux, FT, RSS, and Google News. Duplicate URLs and similar headlines are removed by
the existing content pipeline. Set `TIINGO_NEWS_ENABLED=true` to activate fetching. Because Tiingo plan terms differ
for internal use, retention, and redistribution, archived output remains blocked unless
`TIINGO_ALLOW_PERSISTENCE=true` is also set after confirming the account licence. `TIINGO_LICENSE_MODE=internal` is
written to the audit log as a deployment reminder; it does not grant additional usage rights.

A `200` response from Tiingo's authentication test combined with `403` from the News endpoint means the token is valid
but the account does not currently have News API entitlement. Keep the persistence guard disabled until both endpoint
access and the intended internal-distribution rights are confirmed.

The endpoint contract and current usage terms are documented in the
[Tiingo News API documentation](https://www.tiingo.com/documentation/news),
[authentication guide](https://www.tiingo.com/documentation/general/connecting), and
[Tiingo terms of use](https://api.tiingo.com/tos/).

## Public Headline Sources

WSJ Markets, WSJ World, MarketWatch Top Stories, and MarketWatch MarketPulse are ingested from their public Dow Jones
RSS endpoints. The pipeline stores feed-provided headline metadata and original links; it does not bypass subscriptions
or retrieve paywalled article bodies.

Reuters RSS delivery now requires an authenticated Reuters Connect account, so the free configuration uses a
site-restricted Google News query for Reuters links. Yahoo does not publish a supported Yahoo Finance news API and its
Finance help prohibits redistribution of displayed data, so Yahoo Finance is also discovery-only through Google News.
Morningstar uses the same metadata-only discovery path because its public editorial feed availability varies by region.
All three sources still pass through the normal recency, deduplication, source-diversity, and relevance filters.

References: [Reuters RSS delivery](https://liaison.thomsonreuters.com/page/rss-feeds-tech-notes),
[Yahoo Finance data terms](https://help.yahoo.com/kb/finance/exchanges-data-providers-yahoo-finance-sln2310.html), and
[Morningstar RSS overview](https://my.morningstar.com/my/feeds/rssintro.aspx).

## Editorial Narrative Signal

The narrative model runs after article normalization, deduplication, ranking, and portfolio enrichment. It measures
bigram and trigram document frequency across distinct publishers, then compares the current news corpus with up to eight
prior weekly snapshots. Signals are labelled `Emerging`, `Accelerating`, `Persistent`, `Fading`, or `Establishing`.
They describe changes in coverage intensity, not market direction or a trading recommendation.

This model is an internal story-selection signal rather than a reader-facing
newsletter section. Reader-facing change detection appears through What Changed
This Week and Dislocation Watch.

Settings live in `config/narrative_monitor.yaml`. Local aggregate history is stored in the gitignored
`data/trends/ngram_history.json`; GitHub Actions restores that file through a small workflow cache so the Monday run can
maintain its rolling baseline. The current section and its audit metadata are written to:

```text
output/latest/narrative_trends.json
output/latest/audit_log.json
```

The implementation uses the Python standard library, so it adds no model package or runtime dependency.

## Portfolio-Aware Mode

The newsletter can rank headlines and frame commentary around current portfolio exposures. The default sample portfolio is:

```text
examples/current_portfolio.csv
```

The equity monitor uses:

```text
data/portfolio/equity_holdings.csv
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

When portfolio mode is enabled, the newsletter adds Portfolio Snapshot, Equity Holdings Monitor, Chart of the Week, Portfolio-Linked News, Regional Headlines, and a portfolio-aware watchlist.

Manual pricing and source limitations are written to:

```text
output/latest/audit_log.json
```

## Production Send

```powershell
$env:SEND_MODE="send"
python -m src.main
```

The send step is blocked if required sections are missing, fewer than five source URLs are present, schema validation fails, or generated text contains failure phrases such as `as an AI` or `I could not`.

For an individual-address company audience, keep one owner/archive mailbox in
`NEWSLETTER_TO` and place the employee list in the private `NEWSLETTER_BCC`
environment variable. Separate addresses with commas or semicolons. The list must
never be committed, pasted into workflow YAML, or placed in `.env.example`.

```text
NEWSLETTER_TO=owner-or-archive@example.com
NEWSLETTER_BCC=employee.one@example.com;employee.two@example.com
ALLOW_COMPANY_SEND=false
MAX_COMPANY_RECIPIENTS=500
```

Company delivery remains blocked until `ALLOW_COMPANY_SEND=true`. Keep it false
through the owner-only review, then store `NEWSLETTER_BCC` as a GitHub Actions
secret and `ALLOW_COMPANY_SEND` as an explicitly approved repository variable.
Only the visible owner/archive address appears in `To`; employee addresses are
deduplicated and routed through BCC.

For Gmail automation, use OAuth send-only access. The Gmail connector used interactively by Codex is separate from GitHub Actions and cannot supply credentials to an unattended workflow.

### Gmail OAuth Setup

1. Enable the Gmail API in a Google Cloud project.
2. Configure the OAuth consent screen and request only `https://www.googleapis.com/auth/gmail.send`.
3. Create and download a Desktop app OAuth client JSON.
4. Install dependencies and run the one-time local authorization:

```powershell
python -m pip install -r requirements.txt
python scripts/configure_gmail_oauth.py "C:\path\to\client_secret.json" `
  --from-email "sender@example.com" `
  --recipient "recipient@example.com"
```

The authorization helper opens Google consent in the browser and saves the client ID, client secret, and refresh token to the gitignored `.env` without printing them. Never commit the downloaded client JSON or `.env`. Store `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN` as GitHub Actions secrets for unattended delivery.

## Add Sources

Edit `config/sources.yaml` to add RSS feeds, source quality scores, or fallback sources. Every article should include title, source, date, URL, summary, and category. Prefer public APIs or publisher-provided RSS; do not add HTML scraping for paywalled article bodies.

## Gmail MCP Newsletter Sources

Gmail is the primary inbox channel for subscribed research. The Gmail label `Wolf Research Sources` is the collection boundary; route trusted newsletters into that label with Gmail filters.

Run the repository skill at `automation/skills/build-wolf-market-brief` to search the last eight days, screen email content as untrusted input, deduplicate coverage, and write normalized metadata to the gitignored `data/inbox/gmail_digest.json` cache. The Python pipeline merges that cache with Marketaux, official RSS feeds, Google News discovery, FRED, and Alpha Vantage.

The skill may create a reviewed Gmail draft after validation. It never sends automatically, and the standard application remains in `SEND_MODE=dry_run` unless delivery is explicitly enabled.

## Update Sections

Edit `config/newsletter.yaml` for required sections and newsletter settings. Section prompts live in `src/llm/prompts.py`; structured schemas live in `src/llm/schemas.py`.

## Email Design Preview

The publication-style HTML email template lives at `templates/newsletter.html.j2`, with email-safe CSS in `assets/newsletter.css`. It uses a paper editorial layout, a dark Macro Pulse feature, sourced charts, compact market tape, and regional desk sections.

Generate a preview:

```powershell
python scripts/preview_design.py
```

When `output/latest/newsletter.json` exists, the preview reuses it so the preview and latest newsletter share identical content without consuming APIs twice.

The preview is saved to:

```text
output/design_preview/newsletter_preview.html
```

## GitHub Pages Preview

The `Pages Preview` workflow publishes a static synthetic sample to GitHub Pages.
It renders `examples/public_preview_newsletter.json`, never the current internal
edition or portfolio data. It deploys only the sanitized HTML and public FRED
chart from `public_preview/`; it does not publish `.env`, audit logs, JSON outputs,
raw keys, current internal headlines, or real portfolio sections.

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
- `weekly_newsletter.yml` runs every Monday at `01:00 UTC`, equal to `09:00 Singapore time`, validates and sends the finalized V2, and uploads outputs as artifacts. Configure `EMAIL_PROVIDER=gmail_api` as a repository variable and add `GMAIL_FROM_EMAIL`, `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, `NEWSLETTER_TO`, and data-provider keys as Actions secrets.
- `pages_preview.yml` publishes the rendered preview to GitHub Pages.

## Risk And Compliance Notes

This engine is for internal analytical distribution. It should not produce unsupported investment recommendations. Every factual claim should be traceable to a source URL or configured data source. Live API integrations should be reviewed before production use.
