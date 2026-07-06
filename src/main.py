from __future__ import annotations

from src.emailer.send_email import send_email
from src.fetchers.commodities import fetch_commodities_data
from src.fetchers.fx import fetch_fx_data
from src.fetchers.macro import fetch_macro_data
from src.fetchers.news import fetch_news
from src.fetchers.private_markets import fetch_private_markets_news
from src.fetchers.sectors import fetch_sector_scoreboard
from src.llm.generate_sections import generate_sections
from src.processing.dedupe import dedupe_articles
from src.processing.rank import rank_articles
from src.processing.validate import run_quality_checks
from src.render.assemble_newsletter import assemble_newsletter, newsletter_to_html, newsletter_to_markdown
from src.utils.dates import archive_date
from src.utils.io import load_yaml, project_path, write_json, write_text
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


def build_newsletter() -> dict:
    newsletter_config = load_yaml("config/newsletter.yaml")
    sources_config = load_yaml("config/sources.yaml")
    tickers_config = load_yaml("config/tickers.yaml")
    lookback_days = int(newsletter_config.get("lookback_days", 7))

    news = fetch_news(sources_config, lookback_days)
    private_news = fetch_private_markets_news(sources_config, lookback_days)
    all_articles = dedupe_articles(news + private_news)
    ranked_articles = rank_articles(all_articles, sources_config.get("source_quality", {}))

    data = {
        "macro": fetch_macro_data(),
        "fx": fetch_fx_data(tickers_config),
        "commodities": fetch_commodities_data(tickers_config),
        "sectors": fetch_sector_scoreboard(tickers_config),
        "private_markets": private_news,
        "ranked_articles": ranked_articles,
    }
    sections = generate_sections(data)
    draft = {
        "title": newsletter_config["title"],
        "sections": sections,
    }
    warnings = run_quality_checks(draft, newsletter_config["required_sections"])
    newsletter = assemble_newsletter(newsletter_config["title"], newsletter_config["timezone"], sections, warnings)
    return newsletter.model_dump(mode="json")


def save_outputs(newsletter_dict: dict) -> dict:
    newsletter = assemble_newsletter(
        newsletter_dict["title"],
        newsletter_dict["timezone"],
        newsletter_dict["sections"],
        newsletter_dict.get("warnings", []),
    )
    markdown = newsletter_to_markdown(newsletter)
    html = newsletter_to_html(newsletter)
    archive = archive_date(newsletter.timezone)

    latest_dir = project_path("output", "latest")
    archive_dir = project_path("output", "archive", archive)
    write_json(latest_dir / "newsletter.json", newsletter.model_dump(mode="json"))
    write_text(latest_dir / "newsletter.md", markdown)
    write_text(latest_dir / "newsletter.html", html)
    write_json(archive_dir / "newsletter.json", newsletter.model_dump(mode="json"))
    write_text(archive_dir / "newsletter.md", markdown)
    return {"markdown": markdown, "html": html, "archive": archive}


def main() -> None:
    config = load_yaml("config/newsletter.yaml")
    newsletter = build_newsletter()
    rendered = save_outputs(newsletter)
    recipients = config.get("recipients", [])
    result = send_email(config["title"], rendered["html"], recipients, newsletter.get("warnings", []))
    LOGGER.info("Newsletter generated. Email result: %s", result)


if __name__ == "__main__":
    main()
