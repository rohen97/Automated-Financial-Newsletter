from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def now_in_timezone(timezone: str = "Asia/Singapore") -> datetime:
    return datetime.now(ZoneInfo(timezone))


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def is_within_days(value: datetime | None, days: int, now: datetime | None = None) -> bool:
    if value is None:
        return True
    now = now or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value >= now - timedelta(days=days)


def archive_date(timezone: str = "Asia/Singapore") -> str:
    return now_in_timezone(timezone).date().isoformat()
