from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime
import time
from typing import Any, Callable

from src.pipeline.cache import TTLFileCache
from src.pipeline.executors import ExecutorManager
from src.pipeline.models import PipelineContext, ProviderResult, StageResult, readonly_mapping
from src.pipeline.timing import TimingCollector, stage_timer
from src.utils.dates import parse_date


@dataclass(frozen=True)
class ProviderStage:
    name: str
    provider: str
    loader: Callable[[], Any]
    fallback: Any
    cache_ttl_hours: float = 0.0
    cache_payload: Any = None
    cache_allowed: bool = True
    decode_cached: Callable[[Any], Any] | None = None
    encode_cached: Callable[[Any], Any] | None = None


async def fetch_all_external_data(
    context: PipelineContext,
    stages: list[ProviderStage],
    *,
    cache: TTLFileCache,
    executors: ExecutorManager,
    timings: TimingCollector,
) -> dict[str, ProviderResult]:
    total_limit = max(1, int(context.performance.get("max_total_io_concurrency", 12)))
    total_semaphore = asyncio.Semaphore(total_limit)
    provider_semaphores = {
        provider: asyncio.Semaphore(
            max(1, int((context.provider_limits.get(provider) or {}).get("max_concurrency", 1)))
        )
        for provider in {stage.provider for stage in stages}
    }
    tasks = [
        _run_provider_stage(
            context,
            stage,
            cache=cache,
            executors=executors,
            timings=timings,
            total_semaphore=total_semaphore,
            provider_semaphore=provider_semaphores[stage.provider],
        )
        for stage in stages
    ]
    if context.performance.get("async_io_enabled", True):
        completed = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        completed = []
        for task in tasks:
            try:
                completed.append(await task)
            except Exception as exc:
                completed.append(exc)
    results: dict[str, ProviderResult] = {}
    for stage, result in zip(stages, completed, strict=True):
        if isinstance(result, Exception):
            results[stage.name] = ProviderResult(
                provider=stage.provider,
                data=stage.fallback,
                errors=(str(result)[:240],),
            )
        else:
            results[stage.name] = result
    return results


def merge_stage_results(results: list[StageResult]) -> dict[str, Any]:
    """Merge explicit stage outputs in caller-defined DAG order."""
    return {result.stage: result.data for result in results}


def article_cache_encode(articles: list[dict]) -> list[dict]:
    encoded = []
    for article in articles:
        row = dict(article)
        published_at = row.get("published_at")
        if isinstance(published_at, (date, datetime)):
            row["published_at"] = published_at.isoformat()
        encoded.append(row)
    return encoded


def article_cache_decode(articles: list[dict]) -> list[dict]:
    decoded = []
    for article in articles or []:
        row = dict(article)
        row["published_at"] = parse_date(row.get("published_at"))
        decoded.append(row)
    return decoded


async def _run_provider_stage(
    context: PipelineContext,
    stage: ProviderStage,
    *,
    cache: TTLFileCache,
    executors: ExecutorManager,
    timings: TimingCollector,
    total_semaphore: asyncio.Semaphore,
    provider_semaphore: asyncio.Semaphore,
) -> ProviderResult:
    key = cache.cache_key(
        {
            "stage": stage.name,
            "date": date.today().isoformat(),
            "lookback_days": context.lookback_days,
            "payload": stage.cache_payload,
        }
    )
    if stage.cache_allowed:
        cached = cache.get(stage.name, key, stage.cache_ttl_hours)
        if cached is not None:
            data = stage.decode_cached(cached) if stage.decode_cached else cached
            return ProviderResult(provider=stage.provider, data=data, cache_status="hit")
    else:
        cache.metrics.disable(stage.name)

    started = time.perf_counter()
    try:
        async with total_semaphore, provider_semaphore:
            with stage_timer(f"provider.{stage.name}", timings):
                data = await executors.run_blocking(stage.loader)
        if stage.cache_allowed and stage.cache_ttl_hours > 0:
            encoded = stage.encode_cached(data) if stage.encode_cached else data
            cache.set(stage.name, key, encoded)
        return ProviderResult(
            provider=stage.provider,
            data=data,
            cache_status="miss",
            duration_seconds=round(time.perf_counter() - started, 4),
        )
    except Exception as exc:
        return ProviderResult(
            provider=stage.provider,
            data=stage.fallback,
            cache_status="error",
            errors=(str(exc)[:240],),
            duration_seconds=round(time.perf_counter() - started, 4),
        )


def stage_result(
    stage: str,
    data: Any,
    *,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
    metrics: dict[str, Any] | None = None,
) -> StageResult:
    return StageResult(
        stage=stage,
        data=data,
        warnings=tuple(warnings or ()),
        errors=tuple(errors or ()),
        metrics=readonly_mapping(metrics),
    )
