from __future__ import annotations

from datetime import date


def select_rotation_order(rotation: list[str], today: date | None = None) -> tuple[str | None, list[str], int]:
    """Pick the primary source by ISO week, then try the remaining sources in order."""
    if not rotation:
        return None, [], (today or date.today()).isocalendar().week
    week_number = (today or date.today()).isocalendar().week
    start = week_number % len(rotation)
    ordered = rotation[start:] + rotation[:start]
    return ordered[0], ordered, week_number
