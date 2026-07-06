from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


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
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, default=str)


def write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
