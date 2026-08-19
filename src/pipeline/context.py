from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import uuid4

from src.pipeline.models import PipelineContext
from src.utils.env import load_local_env
from src.utils.io import load_yaml, project_path


CONFIG_PATHS = {
    "newsletter": "config/newsletter.yaml",
    "sources": "config/sources.yaml",
    "tickers": "config/tickers.yaml",
    "portfolio": "config/portfolio.yaml",
    "portfolio_data": "data/portfolio/portfolio_config.yaml",
    "charts": "config/charts.yaml",
    "narrative": "config/narrative_monitor.yaml",
    "performance": "config/performance.yaml",
}


def load_pipeline_context(root: Path | None = None) -> PipelineContext:
    load_local_env()
    configs = {name: deepcopy(load_yaml(path)) for name, path in CONFIG_PATHS.items()}
    newsletter = configs["newsletter"]
    performance_config = configs["performance"]
    performance = dict(performance_config.get("performance") or {})
    provider_limits = dict(performance_config.get("provider_limits") or {})
    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
    project_root = root or project_path()
    run_directory = project_root / "output" / ".pipeline" / run_id
    return PipelineContext(
        root=project_root,
        run_id=run_id,
        run_directory=run_directory,
        timezone=str(newsletter.get("timezone", "Asia/Singapore")),
        lookback_days=int(newsletter.get("lookback_days", 7)),
        configs=MappingProxyType(configs),
        performance=MappingProxyType(performance),
        provider_limits=MappingProxyType(provider_limits),
    )


def config_dict(context: PipelineContext, name: str) -> dict[str, Any]:
    return deepcopy(dict(context.configs.get(name) or {}))
