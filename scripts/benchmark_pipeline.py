from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from pathlib import Path
import shutil
import sys
from threading import Lock
import time
from types import MappingProxyType
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.serialization import compact_json_dumps, write_json_atomic  # noqa: E402
from src.pipeline.cache import TTLFileCache  # noqa: E402
from src.pipeline.executors import ExecutorManager  # noqa: E402
from src.pipeline.memory import MemoryTracker, compact_articles  # noqa: E402
from src.pipeline.models import PipelineContext  # noqa: E402
from src.pipeline.stages import ProviderStage, fetch_all_external_data  # noqa: E402
from src.pipeline.timing import TimingCollector  # noqa: E402
from src.processing.dedupe import dedupe_articles  # noqa: E402


MOCK_PROVIDERS = {
    "fred": 0.18,
    "alpha_vantage": 0.20,
    "marketaux": 0.17,
    "rss": 0.13,
    "external_charts": 0.15,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the newsletter execution primitives.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run the real pipeline once after the quota-safe mocked benchmark.",
    )
    args = parser.parse_args()
    output = run_mocked_benchmark()
    if args.live:
        output["live"] = run_live_pipeline()
    destination = ROOT / "output" / "latest" / "performance_benchmark.json"
    write_json_atomic(destination, output)
    print(compact_json_dumps(output, pretty=True))


def run_mocked_benchmark() -> dict:
    temporary_root = ROOT / "output" / ".pipeline" / f"benchmark-{uuid4().hex}"
    temporary_root.mkdir(parents=True, exist_ok=True)
    calls: Counter[str] = Counter()
    calls_lock = Lock()
    memory = MemoryTracker()
    memory.start()
    try:
        context = _context(temporary_root)
        cache = TTLFileCache(temporary_root / "cache")
        stages = _stages(calls, calls_lock)

        sequential_started = time.perf_counter()
        for stage in stages:
            stage.loader()
        sequential_seconds = time.perf_counter() - sequential_started
        calls.clear()

        cold = asyncio.run(_run_fetch(context, stages, cache))
        cold_calls = dict(calls)
        calls.clear()
        warm = asyncio.run(_run_fetch(context, stages, cache))
        warm_calls = dict(calls)

        processing_started = time.perf_counter()
        article_rows = [
            {
                "title": uuid4().hex,
                "url": f"https://example.test/{index}",
                "source": "Benchmark",
                "region": "Global",
                "raw_payload": {"unused": "x" * 250},
            }
            for index in range(500)
        ]
        deduped = dedupe_articles(article_rows)
        compacted, compact_report = compact_articles(deduped)
        processing_seconds = time.perf_counter() - processing_started

        rendering_started = time.perf_counter()
        rendered = compact_json_dumps({"articles": compacted})
        rendering_seconds = time.perf_counter() - rendering_started

        writing_started = time.perf_counter()
        write_json_atomic(temporary_root / "benchmark_artifact.json", {"bytes": len(rendered)})
        output_writing_seconds = time.perf_counter() - writing_started
        memory_metrics = memory.stop()
        cache_metrics = cache.metrics.snapshot()
        total_cache_reads = cache_metrics["cache_hits"] + cache_metrics["cache_misses"]

        return {
            "mode": "mocked",
            "paid_api_calls": 0,
            "sequential_no_cache": {
                "total_runtime_seconds": round(sequential_seconds, 4),
                "api_calls": len(stages),
            },
            "cold_async": {
                **cold,
                "api_calls_by_provider": cold_calls,
            },
            "warm_cache": {
                **warm,
                "api_calls_by_provider": warm_calls,
            },
            "processing_time_seconds": round(processing_seconds, 6),
            "rendering_time_seconds": round(rendering_seconds, 6),
            "output_writing_time_seconds": round(output_writing_seconds, 6),
            "cache_hit_rate": round(cache_metrics["cache_hits"] / max(total_cache_reads, 1), 4),
            "cache_metrics": cache_metrics,
            "memory": memory_metrics,
            "memory_compaction": compact_report,
            "cold_speedup_vs_sequential": round(
                sequential_seconds / max(cold["total_runtime_seconds"], 0.000001),
                2,
            ),
            "warm_speedup_vs_sequential": round(
                sequential_seconds / max(warm["total_runtime_seconds"], 0.000001),
                2,
            ),
        }
    finally:
        resolved = temporary_root.resolve()
        if ".pipeline" in {part.casefold() for part in resolved.parts}:
            shutil.rmtree(resolved, ignore_errors=True)


async def _run_fetch(
    context: PipelineContext,
    stages: list[ProviderStage],
    cache: TTLFileCache,
) -> dict:
    timings = TimingCollector()
    started = time.perf_counter()
    with ExecutorManager(max_io_workers=8, max_cpu_workers=1) as executors:
        results = await fetch_all_external_data(
            context,
            stages,
            cache=cache,
            executors=executors,
            timings=timings,
        )
    elapsed = time.perf_counter() - started
    return {
        "total_runtime_seconds": round(elapsed, 4),
        "provider_fetch_time_seconds": round(
            sum(timings.snapshot().values()),
            4,
        ),
        "provider_status": {
            name: "ok" if not result.errors else "degraded"
            for name, result in results.items()
        },
        "cache_status": {name: result.cache_status for name, result in results.items()},
    }


def _stages(calls: Counter[str], lock: Lock) -> list[ProviderStage]:
    def loader(provider: str, delay: float):
        def load():
            with lock:
                calls[provider] += 1
            time.sleep(delay)
            return [{"provider": provider, "value": 1}]

        return load

    return [
        ProviderStage(
            name=provider,
            provider=provider,
            loader=loader(provider, delay),
            fallback=[],
            cache_ttl_hours=1,
            cache_payload={"benchmark": True, "provider": provider},
        )
        for provider, delay in MOCK_PROVIDERS.items()
    ]


def _context(root: Path) -> PipelineContext:
    provider_limits = {
        provider: {"max_concurrency": 2}
        for provider in MOCK_PROVIDERS
    }
    return PipelineContext(
        root=root,
        run_id="benchmark",
        run_directory=root / "run",
        timezone="Asia/Singapore",
        lookback_days=7,
        configs=MappingProxyType({}),
        performance=MappingProxyType({"max_total_io_concurrency": 8}),
        provider_limits=MappingProxyType(provider_limits),
    )


def run_live_pipeline() -> dict:
    from src.main import build_newsletter

    started = time.perf_counter()
    newsletter = build_newsletter()
    return {
        "total_runtime_seconds": round(time.perf_counter() - started, 4),
        "pipeline_runtime": newsletter.get("_pipeline_runtime", {}),
    }


if __name__ == "__main__":
    main()
