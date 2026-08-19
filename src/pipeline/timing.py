from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import Lock
import time
from typing import Iterator


@dataclass
class TimingCollector:
    _timings: dict[str, float] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def record(self, stage: str, seconds: float) -> None:
        with self._lock:
            self._timings[stage] = self._timings.get(stage, 0.0) + seconds

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {key: round(value, 4) for key, value in sorted(self._timings.items())}


@contextmanager
def stage_timer(stage: str, collector: TimingCollector) -> Iterator[None]:
    started = time.perf_counter()
    try:
        yield
    finally:
        collector.record(stage, time.perf_counter() - started)
