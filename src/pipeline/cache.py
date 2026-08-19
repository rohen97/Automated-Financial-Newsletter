from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from threading import Lock
import time
from typing import Any

from src.io.serialization import read_json_cached, write_json_atomic


SECRET_MARKERS = ("api_key", "apikey", "client_secret", "refresh_token", "password", "authorization")


@dataclass
class CacheMetrics:
    hits: int = 0
    misses: int = 0
    expired: int = 0
    writes: int = 0
    disabled_providers: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def increment(self, field_name: str) -> None:
        with self._lock:
            setattr(self, field_name, getattr(self, field_name) + 1)

    def disable(self, provider: str) -> None:
        with self._lock:
            self.disabled_providers.add(provider)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cache_hits": self.hits,
                "cache_misses": self.misses,
                "cache_expired": self.expired,
                "cache_writes": self.writes,
                "cache_disabled_providers": sorted(self.disabled_providers),
            }


class TTLFileCache:
    def __init__(
        self,
        root: Path,
        *,
        enabled: bool = True,
        max_entries_per_provider: int = 64,
    ) -> None:
        self.root = root
        self.enabled = enabled
        self.max_entries_per_provider = max(1, max_entries_per_provider)
        self.metrics = CacheMetrics()
        self._provider_locks: dict[str, Lock] = {}
        self._locks_guard = Lock()

    def get(self, provider: str, key: str, ttl_hours: float) -> Any | None:
        if not self.enabled or ttl_hours <= 0:
            self.metrics.disable(provider)
            return None
        target = self._path(provider, key)
        with self._lock_for(provider):
            envelope = read_json_cached(target)
        if not isinstance(envelope, dict):
            self.metrics.increment("misses")
            return None
        created_at = float(envelope.get("created_epoch") or 0)
        if time.time() - created_at > ttl_hours * 3600:
            self.metrics.increment("expired")
            self.metrics.increment("misses")
            return None
        self.metrics.increment("hits")
        return envelope.get("payload")

    def set(self, provider: str, key: str, payload: Any) -> bool:
        if not self.enabled:
            self.metrics.disable(provider)
            return False
        if contains_secret(payload):
            raise ValueError(f"Refusing to cache secret-bearing payload for {provider}")
        target = self._path(provider, key)
        envelope = {
            "provider": provider,
            "created_at": datetime.now(UTC).isoformat(),
            "created_epoch": time.time(),
            "payload": payload,
        }
        with self._lock_for(provider):
            write_json_atomic(target, envelope, pretty=False)
            self._prune(provider)
        self.metrics.increment("writes")
        return True

    def cache_key(self, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _path(self, provider: str, key: str) -> Path:
        safe_provider = "".join(char for char in provider if char.isalnum() or char in {"-", "_"})
        return self.root / safe_provider / f"{key}.json"

    def _lock_for(self, provider: str) -> Lock:
        with self._locks_guard:
            return self._provider_locks.setdefault(provider, Lock())

    def _prune(self, provider: str) -> None:
        provider_directory = self.root / provider
        if not provider_directory.exists():
            return
        files = sorted(
            provider_directory.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for stale in files[self.max_entries_per_provider :]:
            stale.unlink(missing_ok=True)


def contains_secret(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = str(key).casefold()
            if (
                any(marker in normalized for marker in SECRET_MARKERS)
                and value is not None
                and value != ""
                and value is not False
            ):
                return True
            if contains_secret(value):
                return True
    elif isinstance(payload, (list, tuple)):
        return any(contains_secret(item) for item in payload)
    return False
