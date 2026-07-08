from __future__ import annotations

import os
from pathlib import Path


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(dotenv_path=Path(".env"), override=False)


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def live_fetch_enabled(config: dict) -> bool:
    return env_flag("LIVE_FETCH", bool(config.get("live_fetch", False)))
