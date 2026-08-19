from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def compact_json_dumps(data: Any, *, pretty: bool = False) -> str:
    try:
        import orjson

        option = orjson.OPT_INDENT_2 if pretty else 0
        return orjson.dumps(data, option=option, default=str).decode("utf-8")
    except ImportError:
        return json.dumps(
            data,
            indent=2 if pretty else None,
            ensure_ascii=False,
            default=str,
            separators=None if pretty else (",", ":"),
        )


def write_text_atomic(path: str | Path, content: str) -> None:
    _atomic_write(Path(path), content.encode("utf-8"))


def write_bytes_atomic(path: str | Path, content: bytes) -> None:
    _atomic_write(Path(path), content)


def write_json_atomic(path: str | Path, data: Any, *, pretty: bool = True) -> None:
    write_text_atomic(path, compact_json_dumps(data, pretty=pretty))


def read_json_cached(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def read_csv_optimized(
    path: str | Path,
    *,
    usecols: list[str] | None = None,
    dtype: dict[str, str] | None = None,
) -> Any:
    """Read only required CSV columns, using pandas when it is already available."""
    target = Path(path)
    try:
        import pandas as pd

        return pd.read_csv(target, usecols=usecols, dtype=dtype, low_memory=False)
    except ImportError:
        with target.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            if usecols is None:
                return list(rows)
            return [{key: row.get(key) for key in usecols} for row in rows]


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
