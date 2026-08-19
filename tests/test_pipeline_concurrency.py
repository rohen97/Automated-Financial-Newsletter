import asyncio
from pathlib import Path
from threading import Lock
import time
from types import MappingProxyType

from src.pipeline.cache import TTLFileCache
from src.pipeline.executors import ExecutorManager
from src.pipeline.models import PipelineContext, StageResult
from src.pipeline.stages import ProviderStage, fetch_all_external_data, merge_stage_results
from src.pipeline.timing import TimingCollector


def _context(
    tmp_path: Path,
    *,
    total_limit: int = 4,
    provider_limit: int = 2,
    async_enabled: bool = True,
):
    return PipelineContext(
        root=tmp_path,
        run_id="test",
        run_directory=tmp_path / "run",
        timezone="Asia/Singapore",
        lookback_days=7,
        configs=MappingProxyType({}),
        performance=MappingProxyType(
            {
                "max_total_io_concurrency": total_limit,
                "async_io_enabled": async_enabled,
            }
        ),
        provider_limits=MappingProxyType(
            {"test_provider": {"max_concurrency": provider_limit}}
        ),
    )


def _run(
    tmp_path,
    stages,
    *,
    total_limit=4,
    provider_limit=2,
    async_enabled=True,
):
    async def execute():
        with ExecutorManager(max_io_workers=4, max_cpu_workers=1) as executors:
            return await fetch_all_external_data(
                _context(
                    tmp_path,
                    total_limit=total_limit,
                    provider_limit=provider_limit,
                    async_enabled=async_enabled,
                ),
                stages,
                cache=TTLFileCache(tmp_path / "cache", enabled=False),
                executors=executors,
                timings=TimingCollector(),
            )

    return asyncio.run(execute())


def test_independent_provider_calls_run_concurrently(tmp_path):
    def slow(value):
        time.sleep(0.12)
        return value

    stages = [
        ProviderStage(f"stage_{index}", "test_provider", lambda i=index: slow(i), None)
        for index in range(3)
    ]
    started = time.perf_counter()
    results = _run(tmp_path, stages, provider_limit=3)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.29
    assert [results[f"stage_{index}"].data for index in range(3)] == [0, 1, 2]


def test_provider_failure_isolated_and_rate_limit_respected(tmp_path):
    lock = Lock()
    active = 0
    peak = 0

    def bounded(value):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.06)
        with lock:
            active -= 1
        if value == 2:
            raise RuntimeError("provider unavailable")
        return value

    stages = [
        ProviderStage(
            f"stage_{index}",
            "test_provider",
            lambda i=index: bounded(i),
            "fallback",
        )
        for index in range(4)
    ]
    results = _run(tmp_path, stages, provider_limit=2)

    assert peak == 2
    assert results["stage_0"].data == 0
    assert results["stage_2"].data == "fallback"
    assert results["stage_2"].errors == ("provider unavailable",)


def test_stage_result_merge_preserves_dag_order():
    merged = merge_stage_results(
        [
            StageResult(stage="portfolio", data=["holding"]),
            StageResult(stage="news", data=["article"]),
            StageResult(stage="sections", data={"title": "Brief"}),
        ]
    )

    assert list(merged) == ["portfolio", "news", "sections"]


def test_async_execution_can_be_disabled_for_diagnostics(tmp_path):
    timestamps = []

    def record(index):
        timestamps.append((index, time.perf_counter()))
        time.sleep(0.03)
        return index

    stages = [
        ProviderStage(
            f"stage_{index}",
            "test_provider",
            lambda i=index: record(i),
            None,
        )
        for index in range(3)
    ]
    started = time.perf_counter()
    _run(tmp_path, stages, provider_limit=3, async_enabled=False)

    assert time.perf_counter() - started >= 0.085
    assert [index for index, _ in timestamps] == [0, 1, 2]
