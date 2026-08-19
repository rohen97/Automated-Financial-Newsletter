from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from functools import partial
from typing import Any, Callable


class ExecutorManager:
    def __init__(self, *, max_io_workers: int, max_cpu_workers: int) -> None:
        self.max_io_workers = max(1, max_io_workers)
        self.max_cpu_workers = max(1, max_cpu_workers)
        self._threads = ThreadPoolExecutor(
            max_workers=self.max_io_workers,
            thread_name_prefix="wolf-io",
        )
        self._processes: ProcessPoolExecutor | None = None

    async def run_blocking(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._threads, partial(function, *args, **kwargs))

    async def run_cpu(
        self,
        function: Callable[..., Any],
        *args: Any,
        use_process: bool = False,
        **kwargs: Any,
    ) -> Any:
        loop = asyncio.get_running_loop()
        if use_process:
            if self._processes is None:
                self._processes = ProcessPoolExecutor(max_workers=self.max_cpu_workers)
            return await loop.run_in_executor(
                self._processes,
                partial(function, *args, **kwargs),
            )
        return await loop.run_in_executor(self._threads, partial(function, *args, **kwargs))

    def close(self) -> None:
        self._threads.shutdown(wait=True, cancel_futures=True)
        if self._processes is not None:
            self._processes.shutdown(wait=True, cancel_futures=True)

    def __enter__(self) -> ExecutorManager:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
