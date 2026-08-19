from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path
import shutil
from threading import Lock
from typing import Any, Iterable

from src.io.serialization import write_bytes_atomic, write_json_atomic
from src.pipeline.errors import ArtifactWriteError
from src.pipeline.models import NewsletterArtifact, OutputManifest


class OutputWriter:
    """The only publisher allowed to write finalized newsletter artifacts."""

    _writer_lock = Lock()

    def __init__(self, latest_directory: Path, archive_directory: Path) -> None:
        self.latest_directory = latest_directory
        self.archive_directory = archive_directory

    def write(
        self,
        artifacts: Iterable[NewsletterArtifact],
        *,
        provider_status: dict[str, Any],
        validation_status: str,
        send_blocked: bool,
        run_duration_seconds: float,
        generated_at: str,
        cleanup_directory: Path | None = None,
    ) -> OutputManifest:
        with self._writer_lock:
            try:
                manifest = self._write_locked(
                    tuple(artifacts),
                    provider_status=provider_status,
                    validation_status=validation_status,
                    send_blocked=send_blocked,
                    run_duration_seconds=run_duration_seconds,
                    generated_at=generated_at,
                )
            except Exception as exc:
                raise ArtifactWriteError(str(exc)) from exc
        if cleanup_directory is not None:
            _cleanup_run_directory(cleanup_directory)
        return manifest

    def _write_locked(
        self,
        artifacts: tuple[NewsletterArtifact, ...],
        *,
        provider_status: dict[str, Any],
        validation_status: str,
        send_blocked: bool,
        run_duration_seconds: float,
        generated_at: str,
    ) -> OutputManifest:
        files_written: list[str] = []
        file_sizes: dict[str, int] = {}
        checksums: dict[str, str] = {}
        for artifact in artifacts:
            relative = Path(artifact.relative_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Invalid artifact path: {artifact.relative_path}")
            for base in (self.latest_directory, self.archive_directory):
                target = base / relative
                write_bytes_atomic(target, artifact.content)
                label = target.as_posix()
                files_written.append(label)
                file_sizes[label] = len(artifact.content)
                checksums[label] = hashlib.sha256(artifact.content).hexdigest()

        manifest = OutputManifest(
            generated_at=generated_at or datetime.now(UTC).isoformat(),
            files_written=tuple(files_written),
            file_sizes=file_sizes,
            checksums=checksums,
            provider_status=provider_status,
            validation_status=validation_status,
            send_blocked=send_blocked,
            run_duration_seconds=round(float(run_duration_seconds or 0), 4),
        )
        write_json_atomic(
            self.latest_directory / "manifest.json",
            manifest.as_dict(),
            pretty=True,
        )
        return manifest


def text_artifact(name: str, content: str, media_type: str) -> NewsletterArtifact:
    return NewsletterArtifact(
        name=name,
        relative_path=name,
        content=content.encode("utf-8"),
        media_type=media_type,
    )


def bytes_artifact(name: str, content: bytes, media_type: str) -> NewsletterArtifact:
    return NewsletterArtifact(
        name=name,
        relative_path=name,
        content=content,
        media_type=media_type,
    )


def _cleanup_run_directory(directory: Path) -> None:
    resolved = directory.resolve()
    parts = {part.casefold() for part in resolved.parts}
    if ".pipeline" not in parts or not resolved.exists():
        return
    shutil.rmtree(resolved)
