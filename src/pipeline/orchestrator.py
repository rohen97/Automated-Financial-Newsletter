from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from src.analysis.ngram_trends import build_narrative_monitor
from src.analysis.weekly_delta import build_dislocation_watch, build_weekly_delta
from src.charts.chart_of_week import build_chart_of_the_week
from src.fetchers.commodities import fetch_commodities_data
from src.fetchers.fx import fetch_fx_data
from src.fetchers.macro import fetch_macro_data
from src.fetchers.news import fetch_news
from src.fetchers.private_markets import fetch_private_markets_news
from src.fetchers.provider_audit import provider_audit_snapshot, reset_provider_audit
from src.fetchers.sectors import fetch_sector_scoreboard
from src.llm.generate_sections import generate_sections
from src.pipeline.cache import TTLFileCache
from src.pipeline.context import config_dict, load_pipeline_context
from src.pipeline.executors import ExecutorManager
from src.pipeline.memory import MemoryTracker, compact_articles, recommended_cpu_workers
from src.pipeline.models import PipelineContext, ProviderResult, StageResult
from src.pipeline.stages import (
    ProviderStage,
    article_cache_decode,
    article_cache_encode,
    fetch_all_external_data,
    stage_result,
)
from src.pipeline.timing import TimingCollector, stage_timer
from src.portfolio.equity import equity_monitor, load_equity_holdings
from src.portfolio.exposure import concentration_flags, portfolio_summary
from src.portfolio.load import load_portfolio
from src.portfolio.portfolio_news import portfolio_linked_news, portfolio_watchlist, regional_headlines
from src.portfolio.relevance import enrich_articles_with_portfolio_relevance
from src.processing.dedupe import dedupe_articles
from src.processing.rank import rank_articles
from src.processing.validate import run_quality_checks
from src.render.assemble_newsletter import assemble_newsletter


async def run_newsletter_pipeline(context: PipelineContext | None = None) -> dict[str, Any]:
    context = context or load_pipeline_context()
    started = time.perf_counter()
    timings = TimingCollector()
    memory = MemoryTracker()
    memory.start()
    reset_provider_audit()

    max_io_workers = max(1, int(context.performance.get("max_total_io_concurrency", 12)))
    max_cpu_workers = recommended_cpu_workers(context.performance.get("max_cpu_workers", "auto"))
    cache_enabled = bool(context.performance.get("enable_cache", True)) and not bool(os.getenv("PYTEST_CURRENT_TEST"))
    cache = TTLFileCache(context.root / "data" / "cache", enabled=cache_enabled)

    with ExecutorManager(max_io_workers=max_io_workers, max_cpu_workers=max_cpu_workers) as executors:
        initial = await _run_initial_load(context, executors, timings)
        provider_results = await fetch_all_external_data(
            context,
            _provider_stages(context),
            cache=cache,
            executors=executors,
            timings=timings,
        )
        processed = await _run_processing(
            context,
            initial,
            provider_results,
            executors,
            timings,
        )
        sections_result = await _run_generation(
            context,
            initial,
            provider_results,
            processed,
            executors,
            timings,
        )

    sections = sections_result.data
    newsletter_config = config_dict(context, "newsletter")
    with stage_timer("validation", timings):
        warnings = run_quality_checks(
            {"title": newsletter_config["title"], "sections": sections},
            newsletter_config["required_sections"],
        )
        newsletter = assemble_newsletter(
            newsletter_config["title"],
            newsletter_config["timezone"],
            sections,
            warnings,
        )

    provider_audit = _complete_provider_audit(provider_audit_snapshot(), provider_results)
    pipeline_duration = time.perf_counter() - started
    memory_metrics = memory.stop()
    stage_timings = timings.snapshot()
    pipeline_runtime = {
        "pipeline_duration_seconds": round(pipeline_duration, 4),
        "stage_timings": stage_timings,
        "provider_timings": {
            key.removeprefix("provider."): value for key, value in stage_timings.items() if key.startswith("provider.")
        },
        **memory_metrics,
        **cache.metrics.snapshot(),
        "api_calls_by_provider": _api_call_counts(provider_audit),
        "errors_by_provider": _errors_by_provider(provider_audit.get("errors", [])),
        "warnings_by_stage": _warnings_by_stage([*initial.values(), processed, sections_result]),
        "cpu_workers_used": max_cpu_workers,
        "io_concurrency_used": max_io_workers,
        "provider_status": _provider_status(provider_results, provider_audit),
        "memory_optimization": processed.metrics.get("memory_optimization", {}),
    }
    newsletter_dict = newsletter.model_dump(mode="json")
    newsletter_dict["_runtime_audit"] = {
        "api_keys_detected": _api_key_presence(),
        "tiingo_license_mode": os.getenv("TIINGO_LICENSE_MODE", "internal"),
        "tiingo_persistence_allowed": os.getenv("TIINGO_ALLOW_PERSISTENCE", "false").lower() == "true",
        "article_count_raw": processed.metrics.get("article_count_raw", 0),
        "article_count_deduped": processed.metrics.get("article_count_deduped", 0),
        **provider_audit,
    }
    newsletter_dict["_pipeline_runtime"] = pipeline_runtime
    newsletter_dict["_pipeline_run_directory"] = str(context.run_directory)
    return newsletter_dict


def build_newsletter_sync(context: PipelineContext | None = None) -> dict[str, Any]:
    return asyncio.run(run_newsletter_pipeline(context))


async def _run_initial_load(
    context: PipelineContext,
    executors: ExecutorManager,
    timings: TimingCollector,
) -> dict[str, StageResult]:
    portfolio_config = config_dict(context, "portfolio")
    portfolio_data_config = config_dict(context, "portfolio_data")

    async def load_current_portfolio() -> StageResult:
        with stage_timer("initial.portfolio", timings):
            if not portfolio_config.get("enabled", True):
                return stage_result("portfolio", [])
            holdings = await executors.run_blocking(
                load_portfolio,
                portfolio_config.get("input_path", ""),
            )
            return stage_result("portfolio", holdings, metrics={"rows": len(holdings)})

    async def load_equities() -> StageResult:
        with stage_timer("initial.equity_holdings", timings):
            holdings = await executors.run_blocking(
                load_equity_holdings,
                portfolio_data_config.get(
                    "equity_holdings_path",
                    "data/portfolio/equity_holdings.csv",
                ),
            )
            return stage_result("equity_holdings", holdings, metrics={"rows": len(holdings)})

    portfolio_result, equity_result = await asyncio.gather(
        load_current_portfolio(),
        load_equities(),
    )
    return {"portfolio": portfolio_result, "equity_holdings": equity_result}


def _provider_stages(context: PipelineContext) -> list[ProviderStage]:
    sources = config_dict(context, "sources")
    tickers = config_dict(context, "tickers")
    ttl = dict(context.performance.get("cache_ttl_hours") or {})
    tiingo_cache_allowed = (
        not bool(os.getenv("TIINGO_API_KEY"))
        or os.getenv(
            "TIINGO_ALLOW_PERSISTENCE",
            "false",
        ).lower()
        == "true"
    )
    return [
        ProviderStage(
            "news",
            "marketaux",
            lambda: fetch_news(sources, context.lookback_days),
            [],
            float(ttl.get("marketaux", 2)),
            sources,
            cache_allowed=tiingo_cache_allowed,
            decode_cached=article_cache_decode,
            encode_cached=article_cache_encode,
        ),
        ProviderStage(
            "private_news",
            "marketaux",
            lambda: fetch_private_markets_news(sources, context.lookback_days),
            [],
            float(ttl.get("marketaux", 2)),
            sources.get("rss_feeds", {}).get("private_markets", []),
            decode_cached=article_cache_decode,
            encode_cached=article_cache_encode,
        ),
        ProviderStage(
            "macro",
            "fred",
            fetch_macro_data,
            [],
            float(ttl.get("fred", 24)),
            {"series": "configured"},
        ),
        ProviderStage(
            "fx",
            "alpha_vantage",
            lambda: fetch_fx_data(tickers),
            [],
            float(ttl.get("alpha_vantage", 6)),
            tickers.get("fx", []),
        ),
        ProviderStage(
            "commodities",
            "yahoo_finance",
            lambda: fetch_commodities_data(tickers),
            [],
            float(ttl.get("yahoo_finance", ttl.get("alpha_vantage", 6))),
            tickers.get("commodities", []),
        ),
        ProviderStage(
            "sectors",
            "alpha_vantage",
            lambda: fetch_sector_scoreboard(tickers),
            {"title": "Sector Scoreboard", "regions": []},
            float(ttl.get("alpha_vantage", 6)),
            tickers.get("sector_scoreboard", {}),
        ),
    ]


async def _run_processing(
    context: PipelineContext,
    initial: dict[str, StageResult],
    providers: dict[str, ProviderResult],
    executors: ExecutorManager,
    timings: TimingCollector,
) -> StageResult:
    news = list(providers["news"].data or [])
    private_news = list(providers["private_news"].data or [])
    holdings = list(initial["portfolio"].data or [])
    source_quality = config_dict(context, "sources").get("source_quality", {})

    def process() -> tuple[list[dict], dict[str, int]]:
        # Grain: one row per normalized article. Dedupe before any holding expansion.
        deduped = dedupe_articles(news + private_news)
        ranked = rank_articles(deduped, source_quality)
        ranked = enrich_articles_with_portfolio_relevance(ranked, holdings)
        compacted, memory_report = compact_articles(ranked)
        memory_report.update(
            {
                "article_count_raw": len(news) + len(private_news),
                "article_count_deduped": len(compacted),
            }
        )
        return compacted, memory_report

    with stage_timer("processing.articles", timings):
        ranked, report = await executors.run_cpu(process)
    return stage_result(
        "processed_articles",
        ranked,
        metrics={
            "article_count_raw": report["article_count_raw"],
            "article_count_deduped": report["article_count_deduped"],
            "memory_optimization": report,
        },
    )


async def _run_generation(
    context: PipelineContext,
    initial: dict[str, StageResult],
    providers: dict[str, ProviderResult],
    processed: StageResult,
    executors: ExecutorManager,
    timings: TimingCollector,
) -> StageResult:
    holdings = list(initial["portfolio"].data or [])
    equity_holdings = list(initial["equity_holdings"].data or [])
    ranked = list(processed.data or [])
    private_news = list(providers["private_news"].data or [])
    portfolio_config = config_dict(context, "portfolio")
    narrative_config = config_dict(context, "narrative")

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
    macro_data = list(providers["macro"].data or [])
    fx_data = list(providers["fx"].data or [])
    commodities_data = list(providers["commodities"].data or [])
    sectors_data = providers["sectors"].data or {"title": "Sector Scoreboard", "regions": []}

    with stage_timer("generation.derived", timings):
        linked_task = executors.run_cpu(portfolio_linked_news, equity_holdings, [], ranked)
        regional_task = executors.run_cpu(regional_headlines, ranked)
        watch_task = executors.run_cpu(portfolio_watchlist, equity_holdings)
        narrative_task = executors.run_cpu(
            build_narrative_monitor,
            ranked,
            narrative_config,
            persist_history=not bool(os.getenv("PYTEST_CURRENT_TEST")),
        )
        chart_task = executors.run_cpu(
            build_chart_of_the_week,
            config_dict(context, "charts"),
            articles=ranked,
            equity_monitor=equity_data,
            output_directory=context.run_directory,
            archive=False,
            persist_history=not bool(os.getenv("PYTEST_CURRENT_TEST")),
        )
        linked_news, regional_news, watchlist, narrative_monitor, chart = await asyncio.gather(
            linked_task,
            regional_task,
            watch_task,
            narrative_task,
            chart_task,
        )

    weekly_delta = build_weekly_delta(
        macro_data,
        fx_data,
        commodities_data,
        sectors_data,
    )
    dislocation_watch = build_dislocation_watch(
        macro_data,
        fx_data,
        commodities_data,
        sectors_data,
    )
    data = {
        "macro": macro_data,
        "fx": fx_data,
        "commodities": commodities_data,
        "sectors": sectors_data,
        "chart_of_the_week": chart,
        "weekly_delta": weekly_delta,
        "dislocation_watch": dislocation_watch,
        "narrative_monitor": narrative_monitor,
        "private_markets": private_news,
        "ranked_articles": ranked,
        "portfolio_summary": summary,
        "portfolio_flags": flags,
        "equity_monitor": equity_data,
        "portfolio_linked_news": linked_news,
        "regional_headlines": regional_news,
        "portfolio_watchlist": watchlist,
    }
    openai_limit = max(
        1,
        int((context.provider_limits.get("openai") or {}).get("max_concurrency", 2)),
    )
    openai_semaphore = asyncio.Semaphore(openai_limit)
    async with openai_semaphore:
        with stage_timer("generation.sections", timings):
            sections = await executors.run_blocking(generate_sections, data)
    return stage_result("sections", sections)


def _complete_provider_audit(
    audit: dict[str, Any],
    provider_results: dict[str, ProviderResult],
) -> dict[str, Any]:
    providers = set(audit.get("providers_used", []))
    providers.update(result.provider for result in provider_results.values() if result.data)
    audit["providers_used"] = sorted(providers)
    if not audit.get("fred_series_fetched"):
        audit["fred_series_fetched"] = [
            row.get("series_id")
            for row in (provider_results.get("macro") or ProviderResult("fred", [])).data or []
            if row.get("series_id") and row.get("source", {}).get("name") == "FRED"
        ]
    for name, result in provider_results.items():
        for error in result.errors:
            audit.setdefault("errors", []).append({"provider": name, "message": error})
    return audit


def _api_key_presence() -> dict[str, bool]:
    return {
        name: bool(os.getenv(name))
        for name in (
            "OPENAI_API_KEY",
            "FRED_API_KEY",
            "ALPHA_VANTAGE_API_KEY",
            "MARKETAUX_API_KEY",
            "FT_API_KEY",
            "TIINGO_API_KEY",
        )
    }


def _api_call_counts(audit: dict[str, Any]) -> dict[str, int]:
    return {
        "fred": len(audit.get("fred_series_fetched", [])),
        "alpha_vantage": len(audit.get("alpha_vantage_symbols_fetched", [])),
        "marketaux": len(audit.get("marketaux_queries_run", [])),
        "financial_times": len(audit.get("ft_queries_run", [])),
        "tiingo": len(audit.get("tiingo_requests_run", [])),
        "google_news": len(audit.get("google_news_queries_run", [])),
        "rss": len(audit.get("rss_sources_fetched", [])),
        "openai": 1 if "openai" in audit.get("providers_used", []) else 0,
    }


def _errors_by_provider(errors: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for error in errors:
        provider = str(error.get("provider", "pipeline"))
        counts[provider] = counts.get(provider, 0) + 1
    return counts


def _warnings_by_stage(results: list[StageResult]) -> dict[str, list[str]]:
    return {result.stage: list(result.warnings) for result in results if result.warnings}


def _provider_status(
    results: dict[str, ProviderResult],
    audit: dict[str, Any],
) -> dict[str, Any]:
    statuses = {
        name: {
            "provider": result.provider,
            "status": "ok" if not result.errors else "degraded",
            "cache": result.cache_status,
            "duration_seconds": result.duration_seconds,
        }
        for name, result in results.items()
    }
    error_counts = _errors_by_provider(audit.get("errors", []))
    providers = set(audit.get("providers_used", [])) | set(error_counts)
    for provider in sorted(providers):
        statuses.setdefault(
            provider,
            {
                "provider": provider,
                "status": "degraded" if error_counts.get(provider) else "ok",
                "error_count": error_counts.get(provider, 0),
            },
        )
    return statuses
