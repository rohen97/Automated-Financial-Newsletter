from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


def readonly_mapping(value: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True)
class PipelineContext:
    root: Path
    run_id: str
    run_directory: Path
    timezone: str
    lookback_days: int
    configs: Mapping[str, Any]
    performance: Mapping[str, Any]
    provider_limits: Mapping[str, Any]


@dataclass(frozen=True)
class StageResult:
    stage: str
    data: Any = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=readonly_mapping)

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    data: Any = None
    cache_status: str = "miss"
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class AuditEvent:
    stage: str
    level: str
    message: str
    elapsed_seconds: float | None = None


@dataclass(frozen=True)
class NewsletterArtifact:
    name: str
    relative_path: str
    content: bytes
    media_type: str


@dataclass(frozen=True)
class OutputManifest:
    generated_at: str
    files_written: tuple[str, ...]
    file_sizes: Mapping[str, int]
    checksums: Mapping[str, str]
    provider_status: Mapping[str, Any]
    validation_status: str
    send_blocked: bool
    run_duration_seconds: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "files_written": list(self.files_written),
            "file_sizes": dict(self.file_sizes),
            "checksums": dict(self.checksums),
            "provider_status": dict(self.provider_status),
            "validation_status": self.validation_status,
            "send_blocked": self.send_blocked,
            "run_duration_seconds": self.run_duration_seconds,
        }
