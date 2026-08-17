from __future__ import annotations

import os

from src.emailer.send_email import send_email
from src.charts.chart_of_week import build_chart_of_the_week
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
from src.markets.driver_explainer import BANNED_GENERIC_PHRASES, comments_are_valid

LOGGER = get_logger(__name__)


def build_newsletter() -> dict:
    load_local_env()
    reset_provider_audit()
    newsletter_config = load_yaml("config/newsletter.yaml")
    sources_config = load_yaml("config/sources.yaml")
    tickers_config = load_yaml("config/tickers.yaml")
    portfolio_config = load_yaml("config/portfolio.yaml")
    chart_config = load_yaml("config/charts.yaml")
    lookback_days = int(newsletter_config.get("lookback_days", 7))
    holdings = load_portfolio(portfolio_config.get("input_path", "")) if portfolio_config.get("enabled", True) else []
    portfolio_data_config = load_yaml("data/portfolio/portfolio_config.yaml")
    equity_holdings = load_equity_holdings(portfolio_data_config.get("equity_holdings_path", "data/portfolio/equity_holdings.csv"))

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
    linked_news = portfolio_linked_news(equity_holdings, [], ranked_articles)
    regional_news = regional_headlines(ranked_articles)
    watchlist = portfolio_watchlist()

    data = {
        "macro": fetch_macro_data(),
        "fx": fetch_fx_data(tickers_config),
        "commodities": fetch_commodities_data(tickers_config),
        "sectors": fetch_sector_scoreboard(tickers_config),
        "chart_of_the_week": build_chart_of_the_week(chart_config, articles=ranked_articles, equity_monitor=equity_data),
        "private_markets": private_news,
        "ranked_articles": ranked_articles,
        "portfolio_summary": summary,
        "portfolio_flags": flags,
        "equity_monitor": equity_data,
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
            "FT_API_KEY": bool(os.getenv("FT_API_KEY")),
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
    regional_section = sections.get("regional_headlines", {})
    chart_section = sections.get("chart_of_the_week", {})
    sector_section = sections.get("sector_scoreboard", {})
    fx_section = sections.get("fx_markets", {})
    commodities_section = sections.get("commodities", {})
    audit.update(
        {
            "api_keys_detected": runtime_audit.get("api_keys_detected", {}),
            "providers_used": runtime_audit.get("providers_used", []),
            "fred_series_fetched": runtime_audit.get("fred_series_fetched", []),
            "alpha_vantage_symbols_fetched": runtime_audit.get("alpha_vantage_symbols_fetched", []),
            "marketaux_queries_run": runtime_audit.get("marketaux_queries_run", []),
            "ft_queries_run": runtime_audit.get("ft_queries_run", []),
            "ft_articles_fetched": runtime_audit.get("ft_articles_fetched", 0),
            "google_news_queries_run": runtime_audit.get("google_news_queries_run", []),
            "rss_sources_fetched": runtime_audit.get("rss_sources_fetched", []),
            "gmail_messages_ingested": runtime_audit.get("gmail_messages_ingested", 0),
            "article_count_raw": runtime_audit.get("article_count_raw", 0),
            "article_count_deduped": runtime_audit.get("article_count_deduped", 0),
            "macro_articles_count": len(sections.get("macro_news", {}).get("items", [])),
            "private_markets_articles_count": len(sections.get("private_markets", {}).get("items", [])),
            "real_source_url_count": counts.get("real_source_url_count", 0),
            "fallback_source_count": counts.get("fallback_source_count", 0) + runtime_audit.get("fallback_source_count", 0),
            "portfolio_data_loaded": bool(sections.get("portfolio_snapshot")),
            "equity_holdings_count": equity_section.get("holdings_count", 0),
            "usable_equity_pricing_count": equity_section.get("usable_equity_pricing_count", 0),
            "chart_of_the_week_rendered": bool(sections.get("chart_of_the_week")),
            "chart_of_the_week_enabled": True,
            "chart_source_rotation_week_number": chart_section.get("rotation_week_number"),
            "chart_source_selected": chart_section.get("source_name"),
            "fred_chart_selected": chart_section.get("chart_id"),
            "fred_series_used": chart_section.get("series_used", []),
            "fred_chart_scores": chart_section.get("fred_chart_scores", []),
            "fred_chart_selection_reason": chart_section.get("market_signal_reason"),
            "chart_selection_history_updated": chart_section.get("chart_selection_history_updated", False),
            "chart_source_attempts": chart_section.get("source_attempts", []),
            "chart_extraction_method": chart_section.get("extraction_method"),
            "chart_image_embedding_enabled": chart_section.get("embedded_image", False),
            "chart_image_embedding_compliance_approved": chart_section.get("compliance_approved", False),
            "chart_image_embedded": chart_section.get("embedded_image", False),
            "chart_original_url": chart_section.get("original_url"),
            "chart_local_image_path": chart_section.get("local_image_path"),
            "chart_fallback_mode": chart_section.get("fallback_mode", False),
            "fixed_income_section_enabled": False,
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
            "rss_sources_used": _rss_sources_used(sections),
            "openai_sections_generated": ["executive_snapshot", "story_of_the_week"]
            if "openai" in runtime_audit.get("providers_used", [])
            else [],
            "sections_using_deterministic_fallback": _deterministic_sections(sections),
            "regional_coverage_status": _regional_coverage_status(regional_section),
            "portfolio_linked_coverage_status": "ok"
            if sections.get("portfolio_linked_news", {}).get("items")
            else "no portfolio-linked matches",
            "portfolio_validation_status": "equity pricing usable"
            if equity_section.get("missing_pricing_count", 0) == 0
            else "some equity pricing missing",
            "validation_status": _validation_status(newsletter.model_dump(mode="json"), counts, runtime_audit),
            "send_blocked": True,
            "send_block_reason": _send_block_reason(newsletter.model_dump(mode="json"), counts, runtime_audit),
            "sector_scoreboard_regions": [block.get("region") for block in sector_section.get("regions", [])],
            "sector_scoreboard_rows_count": sum(len(block.get("rows", [])) for block in sector_section.get("regions", [])),
            "sector_scoreboard_provider_used": sector_section.get("provider_used"),
            "sector_scoreboard_missing_proxies": sector_section.get("missing_proxies", []),
            "sector_scoreboard_stale_prices": sector_section.get("stale_prices", []),
            "fx_provider_used": _provider_from_rows(fx_section.get("rows", [])),
            "fx_rows_count": len(fx_section.get("rows", [])),
            "commodities_provider_used": _provider_from_rows(commodities_section.get("rows", [])),
            "commodities_rows_count": len(commodities_section.get("rows", [])),
            "driver_explainer_used": True,
            "driver_comments_generated_by_openai": 0,
            "driver_comments_generated_deterministically": _driver_comment_count(sections),
            "driver_comment_confidence_summary": _driver_confidence_summary(sections),
            "market_driver_sources_used": sorted(set(_provider_from_rows(fx_section.get("rows", []) + commodities_section.get("rows", [])))),
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
    write_text(archive_dir / "newsletter.html", html)
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
    sections = newsletter.get("sections", {})
    market_warning = _market_dashboard_validation(sections)
    if market_warning:
        return market_warning
    if not _has_source_backed_macro(sections):
        return "blocked: Macro News has no real sources"
    if _regions_with_headlines(sections.get("regional_headlines", {})) < 3:
        return "blocked: Regional Headlines has fewer than 3 sourced regions"
    if not sections.get("portfolio_linked_news", {}).get("items"):
        return "blocked: Portfolio-Linked News has no matches"
    if runtime_audit.get("fallback_source_count", 0) and os.getenv("ALLOW_FALLBACK_IN_SEND", "false").lower() != "true":
        return "blocked: fallback active and ALLOW_FALLBACK_IN_SEND=false"
    if newsletter.get("warnings"):
        return "blocked: quality warnings present"
    if "as an ai" in text or "i could not" in text:
        return "blocked: generated text contains disallowed language"
    return "ok"


def _market_dashboard_validation(sections: dict) -> str:
    sector = sections.get("sector_scoreboard", {})
    region_counts = {block.get("region"): len(block.get("rows", [])) for block in sector.get("regions", [])}
    for region in ("US", "Europe", "Asia_APAC"):
        if region_counts.get(region, 0) == 0:
            return f"blocked: Sector Scoreboard has no {region} market rows"
    comments = []
    for row in sections.get("fx_markets", {}).get("rows", []):
        comments.append(str(row.get("driver", "")))
    for row in sections.get("commodities", {}).get("rows", []):
        comments.append(str(row.get("driver", "")))
    for block in sector.get("regions", []):
        for row in block.get("rows", []):
            comments.append(str(row.get("comment", "")))
    if not comments_are_valid(comments):
        return "blocked: market driver comments fail 1W/1M/YTD or banned phrase validation"
    for phrase in BANNED_GENERIC_PHRASES:
        if phrase.lower() in " ".join(comments).lower():
            return f"blocked: market driver comments contain banned phrase {phrase}"
    return ""


def _provider_from_rows(rows: list[dict]) -> list[str]:
    providers = []
    for row in rows:
        source = row.get("source", {})
        provider = row.get("provider") or source.get("name")
        if provider and provider not in providers:
            providers.append(provider)
    return providers


def _driver_comment_count(sections: dict) -> int:
    total = len(sections.get("fx_markets", {}).get("rows", [])) + len(sections.get("commodities", {}).get("rows", []))
    total += sum(len(block.get("rows", [])) for block in sections.get("sector_scoreboard", {}).get("regions", []))
    return total


def _driver_confidence_summary(sections: dict) -> dict:
    scores = []
    for row in sections.get("fx_markets", {}).get("rows", []) + sections.get("commodities", {}).get("rows", []):
        if row.get("confidence_score") is not None:
            scores.append(float(row["confidence_score"]))
    for block in sections.get("sector_scoreboard", {}).get("regions", []):
        for row in block.get("rows", []):
            if row.get("confidence_score") is not None:
                scores.append(float(row["confidence_score"]))
    if not scores:
        return {"count": 0}
    return {"count": len(scores), "min": min(scores), "max": max(scores), "avg": round(sum(scores) / len(scores), 3)}


def _has_source_backed_macro(sections: dict) -> bool:
    for item in sections.get("macro_news", {}).get("items", []):
        for source in item.get("sources", []):
            url = str(source.get("url", ""))
            if url and "example.com/wolf-research" not in url:
                return True
    return False


def _regions_with_headlines(regional_section: dict) -> int:
    return sum(1 for item in regional_section.get("regions", []) if item.get("headlines"))


def _regional_coverage_status(regional_section: dict) -> str:
    count = _regions_with_headlines(regional_section)
    return "ok" if count >= 3 else f"limited: {count} regions with headlines"


def _deterministic_sections(sections: dict) -> list[str]:
    deterministic = []
    if not sections.get("private_markets", {}).get("items"):
        deterministic.append("private_markets")
    if not sections.get("portfolio_linked_news", {}).get("items"):
        deterministic.append("portfolio_linked_news")
    return deterministic


def _rss_sources_used(sections: dict) -> list[str]:
    names = set()
    for section in sections.values():
        if isinstance(section, dict):
            for item in section.get("items", []):
                for source in item.get("sources", []):
                    name = source.get("name")
                    if name and name not in {"Sample Data", "Fallback source"}:
                        names.add(name)
    return sorted(names)


def main() -> None:
    config = load_yaml("config/newsletter.yaml")
    newsletter = build_newsletter()
    rendered = save_outputs(newsletter)
    recipients = config.get("recipients", [])
    result = send_email(config["title"], rendered["html"], recipients, newsletter.get("warnings", []))
    LOGGER.info("Newsletter generated. Email result: %s", result)


if __name__ == "__main__":
    main()
