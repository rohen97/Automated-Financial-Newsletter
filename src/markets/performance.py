from __future__ import annotations

from datetime import date, datetime, timedelta


def pct_return(current: float, previous: float | None) -> float:
    if previous in (None, 0):
        return 0.0
    return round(((current / previous) - 1) * 100, 2)


def get_nearest_available_observation(history: list[dict], target: date) -> dict | None:
    dated = [row for row in history if row.get("date") and row.get("close") is not None]
    if not dated:
        return None
    parsed = [(_parse_date(row["date"]), row) for row in dated]
    eligible = [(observed_at, row) for observed_at, row in parsed if observed_at <= target]
    if eligible:
        return max(eligible, key=lambda item: item[0])[1]
    return min(parsed, key=lambda item: item[0])[1]


def handle_missing_dates(history: list[dict]) -> list[dict]:
    return sorted(
        [row for row in history if row.get("date") and row.get("close") is not None],
        key=lambda row: _parse_date(row["date"]),
    )


def calculate_1w_return(history: list[dict]) -> float:
    return _period_return(history, date.today() - timedelta(days=7))


def calculate_1m_return(history: list[dict]) -> float:
    return _period_return(history, date.today() - timedelta(days=30))


def calculate_ytd_return(history: list[dict]) -> float:
    return _period_return(history, date(date.today().year, 1, 1))


def calculate_return_table(history: list[dict]) -> dict:
    clean = handle_missing_dates(history)
    if not clean:
        raise ValueError("No valid market observations.")
    latest = clean[-1]
    latest_date = _parse_date(latest["date"])
    freshness_days = (date.today() - latest_date).days
    return {
        "latest": round(float(latest["close"]), 4),
        "latest_date": latest_date.isoformat(),
        "one_week": calculate_1w_return(clean),
        "one_month": calculate_1m_return(clean),
        "ytd": calculate_ytd_return(clean),
        "freshness_days": max(0, freshness_days),
        "is_stale": freshness_days > 7,
    }


def _period_return(history: list[dict], target: date) -> float:
    clean = handle_missing_dates(history)
    if not clean:
        return 0.0
    latest = clean[-1]
    ref = get_nearest_available_observation(clean, target)
    return pct_return(float(latest["close"]), float(ref["close"]) if ref else None)


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()
