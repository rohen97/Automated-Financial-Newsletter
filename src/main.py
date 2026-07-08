from __future__ import annotations

import os

from src.emailer.send_email import send_email
from src.fetchers.commodities import fetch_commodities_data
from src.fetchers.fx import fetch_fx_data
from src.fetchers.macro import fetch_macro_data
from src.fetchers.news import fetch_news
from src.fetchers.provider_audit import provider_audit_snapshot, reset_provider_audit, source_counts
from src.fetchers.private_markets import fetch_private_markets_news
from src.fetchers.sectors import fetch_sector_scoreboard
from src.llm.generate_sections import generate_sections
from src.portfolio.equity import equity_monitor, load_equity_holdings
from src.portfolio.exposure import concentration_flags, portfolio_summary
from src.portfolio.fixed_income import fixed_income_monitor, load_fixed_income_issuers
from src.portfolio.load import load_portfolio
from src.portfolio.portfolio_news import portfolio_linked_news, portfolio_watchlist, regional_headlines
from src.portfolio.relevance import enrich_articles_with_portfolio_relevance
from src.processing.dedupe import dedupe_articles
from src.processing.rank import rank_articles
from src.processing.validate import collect_source_urls, run_quality_checks
from src.render.assemble_newsletter import assemble_newsletter, render_newsletter_html, newsletter_to_markdown
from src.utils.dates import archive_date
from src.utils.env import load_local_env
from src.utils.io import load_yaml, project_path, write_json, write_text
from src.utils.logging import get_logger

LOGGER = get_logger(__name__)


def build_newsletter() -> dict:
    load_local_env()
    reset_provider_audit()
    newsletter_config = load_yaml("config/newsletter.yaml")
    sources_config = load_yaml("config/sources.yaml")
    tickers_config = load_yaml("config/tickers.yaml")
    portfolio_config = load_yaml("config/portfolio.yaml")
    portfolio_data_config = load_yaml("data/portfolio/portfolio_config.yaml")
    lookback_days = int(newsletter_config.get("lookback_days", 7))
    holdings = load_portfolio(portfolio_config.get("input_path", "")) if portfolio_config.get("enabled", True) else []
    equity_holdings = load_equity_holdings(portfolio_data_config.get("equity_holdings_path", "data/portfolio/equity_holdings.csv"))
    fixed_income_issuers = load_fixed_income_issuers(portfolio_data_config.get("fixed_income_holdings_path", "data/portfolio/fixed_income_holdings.csv"))

    news = fetch_news(sources_config, lookback_days)
    private_news = fetch_private_markets_news(sources_config, lookback_days)
    raw_article_count = len(news) + len(private_news)
    all_articles = dedupe_articles(news + private_news)
    deduped_article_count = len(all_articles)
    ranked_articles = rank_articles(all_articles, sources_config.get("source_quality", {}))
    ranked_articles = enrich_articles_with_portfolio_relevance(ranked_articles, holdings)
    summary = portfolio_summary(holdings) if holdings else {}
    flags = (
        concentration_flags(
            summary,
            high_threshold=float(portfolio_config.get("risk_flags", {}).get("high_weight_threshold", 0.20)),
            medium_threshold=float(portfolio_config.get("risk_flags", {}).get("medium_weight_threshold", 0.10)),
        )
        if summary
        else []
    )
    equity_data = equity_monitor(equity_holdings)
    fixed_income_data = fixed_income_monitor(fixed_income_issuers)
    linked_news = portfolio_linked_news(equity_holdings, fixed_income_issuers, ranked_articles)
    regional_news = regional_headlines(ranked_articles)
    watchlist = portfolio_watchlist()

    data = {
        "macro": fetch_macro_data(),
        "fx": fetch_fx_data(tickers_config),
        "commodities": fetch_commodities_data(tickers_config),
        "sectors": fetch_sector_scoreboard(tickers_config),
        "private_markets": private_news,
        "ranked_articles": ranked_articles,
        "portfolio_summary": summary,
        "portfolio_flags": flags,
        "equity_monitor": equity_data,
        "fixed_income_monitor": fixed_income_data,
        "portfolio_linked_news": linked_news,
        "regional_headlines": regional_news,
        "portfolio_watchlist": watchlist,
    }
    sections = generate_sections(data)
    draft = {
        "title": newsletter_config["title"],
        "sections": sections,
    }
    warnings = run_quality_checks(draft, newsletter_config["required_sections"])
    newsletter = assemble_newsletter(newsletter_config["title"], newsletter_config["timezone"], sections, warnings)
    newsletter_dict = newsletter.model_dump(mode="json")
    newsletter_dict["_runtime_audit"] = {
        "api_keys_detected": {
            "OPENAI_API_KEY": bool(os.getenv("OPENAI_API_KEY")),
            "FRED_API_KEY": bool(os.getenv("FRED_API_KEY")),
            "ALPHA_VANTAGE_API_KEY": bool(os.getenv("ALPHA_VANTAGE_API_KEY")),
            "MARKETAUX_API_KEY": bool(os.getenv("MARKETAUX_API_KEY")),
        },
        "article_count_raw": raw_article_count,
        "article_count_deduped": deduped_article_count,
        **provider_audit_snapshot(),
    }
    return newsletter_dict


def save_outputs(newsletter_dict: dict) -> dict:
    runtime_audit = newsletter_dict.get("_runtime_audit", {})
    newsletter = assemble_newsletter(
        newsletter_dict["title"],
        newsletter_dict["timezone"],
        newsletter_dict["sections"],
        newsletter_dict.get("warnings", []),
    )
    markdown = newsletter_to_markdown(newsletter)
    html = render_newsletter_html(newsletter)
    archive = archive_date(newsletter.timezone)
    audit = {
        "title": newsletter.title,
        "generated_at": newsletter.generated_at.isoformat(),
        "timezone": newsletter.timezone,
        "source_urls": sorted(collect_source_urls(newsletter.model_dump(mode="json"))),
        "warnings": newsletter.warnings,
    }
    sections = newsletter.model_dump(mode="json").get("sections", {})
    counts = source_counts(newsletter.model_dump(mode="json"))
    equity_section = sections.get("equity_holdings_monitor", {})
    fixed_income_section = sections.get("fixed_income_monitor", {})
    regional_section = sections.get("regional_headlines", {})
    audit.update(
        {
            "api_keys_detected": runtime_audit.get("api_keys_detected", {}),
            "providers_used": runtime_audit.get("providers_used", []),
            "fred_series_fetched": runtime_audit.get("fred_series_fetched", []),
            "alpha_vantage_symbols_fetched": runtime_audit.get("alpha_vantage_symbols_fetched", []),
            "marketaux_queries_run": runtime_audit.get("marketaux_queries_run", []),
            "article_count_raw": runtime_audit.get("article_count_raw", 0),
            "article_count_deduped": runtime_audit.get("article_count_deduped", 0),
            "real_source_url_count": counts.get("real_source_url_count", 0),
            "fallback_source_count": counts.get("fallback_source_count", 0) + runtime_audit.get("fallback_source_count", 0),
            "portfolio_data_loaded": bool(sections.get("portfolio_snapshot")),
            "equity_holdings_count": equity_section.get("holdings_count", 0),
            "usable_equity_pricing_count": equity_section.get("usable_equity_pricing_count", 0),
            "fixed_income_issuer_count": fixed_income_section.get("issuer_count", 0),
            "fixed_income_position_count": fixed_income_section.get("position_count", 0),
            "fixed_income_mode": fixed_income_section.get("mode", "issuer-only"),
            "fixed_income_total_market_value_usd": fixed_income_section.get("total_market_value_usd"),
            "fixed_income_total_gain_loss_usd": fixed_income_section.get("total_gain_loss_usd"),
            "manual_pricing_count": equity_section.get("manual_pricing_count", 0),
            "missing_pricing_count": equity_section.get("missing_pricing_count", 0),
            "invalid_or_manual_holdings": equity_section.get("invalid_or_manual_holdings", []),
            "total_equity_portfolio_value_usd": equity_section.get("total_equity_portfolio_value_usd"),
            "total_ytd_equity_pnl_usd": equity_section.get("total_ytd_equity_pnl_usd"),
            "best_contributor": equity_section.get("best_contributor"),
            "worst_contributor": equity_section.get("worst_contributor"),
            "largest_sector_exposure": equity_section.get("largest_sector_exposure"),
            "largest_currency_exposure": equity_section.get("largest_currency_exposure"),
            "portfolio_linked_articles_count": len(sections.get("portfolio_linked_news", {}).get("items", [])),
            "regional_headline_counts": {
                item.get("region"): len(item.get("headlines", []))
                for item in regional_section.get("regions", [])
            },
            "missing_bond_fields": fixed_income_section.get("missing_bond_fields", []),
            "portfolio_validation_status": f"{fixed_income_section.get('mode', 'issuer-only')} fixed income; equity pricing usable"
            if equity_section.get("missing_pricing_count", 0) == 0
            else f"{fixed_income_section.get('mode', 'issuer-only')} fixed income; some equity pricing missing",
            "validation_status": _validation_status(newsletter.model_dump(mode="json"), counts, runtime_audit),
            "send_blocked": True,
            "send_block_reason": _send_block_reason(newsletter.model_dump(mode="json"), counts, runtime_audit),
            "errors": runtime_audit.get("errors", []),
        }
    )

    latest_dir = project_path("output", "latest")
    archive_dir = project_path("output", "archive", archive)
    write_json(latest_dir / "newsletter.json", newsletter.model_dump(mode="json"))
    write_text(latest_dir / "newsletter.md", markdown)
    write_text(latest_dir / "newsletter.html", html)
    write_json(latest_dir / "source_audit.json", audit)
    write_json(latest_dir / "audit_log.json", audit)
    write_json(archive_dir / "newsletter.json", newsletter.model_dump(mode="json"))
    write_text(archive_dir / "newsletter.md", markdown)
    write_json(archive_dir / "source_audit.json", audit)
    write_json(archive_dir / "audit_log.json", audit)
    return {"markdown": markdown, "html": html, "archive": archive, "audit": audit}


def _send_block_reason(newsletter: dict, counts: dict, runtime_audit: dict) -> str:
    if os.getenv("SEND_MODE", "dry_run") != "send":
        return "SEND_MODE is dry_run"
    validation = _validation_status(newsletter, counts, runtime_audit)
    if validation != "ok":
        return validation
    return ""


def _validation_status(newsletter: dict, counts: dict, runtime_audit: dict) -> str:
    text = newsletter_to_markdown(
        assemble_newsletter(
            newsletter["title"],
            newsletter["timezone"],
            newsletter["sections"],
            newsletter.get("warnings", []),
        )
    ).lower()
    if counts.get("real_source_url_count", 0) < 5:
        return "blocked: real_source_url_count below 5"
    if runtime_audit.get("fallback_source_count", 0) and os.getenv("ALLOW_FALLBACK_IN_SEND", "false").lower() != "true":
        return "blocked: fallback active and ALLOW_FALLBACK_IN_SEND=false"
    if newsletter.get("warnings"):
        return "blocked: quality warnings present"
    if "as an ai" in text or "i could not" in text:
        return "blocked: generated text contains disallowed language"
    return "ok"


def main() -> None:
    config = load_yaml("config/newsletter.yaml")
    newsletter = build_newsletter()
    rendered = save_outputs(newsletter)
    recipients = config.get("recipients", [])
    result = send_email(config["title"], rendered["html"], recipients, newsletter.get("warnings", []))
    LOGGER.info("Newsletter generated. Email result: %s", result)


if __name__ == "__main__":
    main()
