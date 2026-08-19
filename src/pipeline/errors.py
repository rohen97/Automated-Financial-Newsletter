from __future__ import annotations


class PipelineError(RuntimeError):
    """Base error for failures owned by pipeline orchestration."""


class StageExecutionError(PipelineError):
    def __init__(self, stage: str, message: str):
        super().__init__(f"{stage}: {message}")
        self.stage = stage


class ArtifactWriteError(PipelineError):
    """Raised when the single output writer cannot publish an artifact."""
