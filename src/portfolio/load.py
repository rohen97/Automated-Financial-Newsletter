from __future__ import annotations

import csv
from pathlib import Path

from src.utils.io import project_path


REQUIRED_COLUMNS = {"holding", "asset_class", "region", "sector", "currency", "weight"}


def load_portfolio(path: str | Path) -> list[dict]:
    target = Path(path)
    if not target.is_absolute():
        target = project_path(str(target))
    if not target.exists():
        return []

    rows: list[dict] = []
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_COLUMNS.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Portfolio file missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            cleaned = {key: (value or "").strip() for key, value in row.items()}
            cleaned["weight"] = float(cleaned["weight"] or 0)
            rows.append(cleaned)
    return rows
