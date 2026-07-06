from __future__ import annotations


def describe_change(value: float) -> str:
    if value > 0:
        return "higher"
    if value < 0:
        return "lower"
    return "unchanged"


def summarize_market_table(rows: list[dict], name_key: str = "label") -> list[str]:
    bullets = []
    for row in rows[:5]:
        label = row.get(name_key) or row.get("sector") or "Asset"
        week = float(row.get("one_week_change", row.get("one_week", 0)))
        bullets.append(f"{label} moved {describe_change(week)} over the week ({week:+.2f}).")
    return bullets
