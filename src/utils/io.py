from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.io.serialization import write_json_atomic, write_text_atomic


ROOT = Path(__file__).resolve().parents[2]


def project_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def load_yaml(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.is_absolute():
        target = project_path(str(target))
    with target.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def write_json(path: str | Path, data: Any) -> None:
    write_json_atomic(path, data, pretty=True)


def write_text(path: str | Path, content: str) -> None:
    write_text_atomic(path, content)
