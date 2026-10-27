"""Pure deadline conversion. Scheduling still uses Phase 3 durable wait records."""

from datetime import datetime, time, timedelta, timezone, date
from zoneinfo import ZoneInfo
from app.apps.power_apps.runtime import utc as assume_utc


def utc(value):
    return assume_utc(value).astimezone(timezone.utc) if value is not None else None


def deadline(start, seconds, calendar=None):
    start = utc(start)
    if calendar is None:
        return start + timedelta(seconds=seconds)
    zone = ZoneInfo(calendar.timezone)
    instant = start.astimezone(zone)
    holidays = {date.fromisoformat(day) for day in calendar.holidays}
    remaining = float(seconds)
    for _ in range(370):
        day = instant.date()
        opening = datetime.combine(day, time(calendar.opens_at), zone)
        closing = (
            datetime.combine(day + timedelta(days=1), time(0), zone)
            if calendar.closes_at == 24
            else datetime.combine(day, time(calendar.closes_at), zone)
        )
        if day.weekday() in calendar.weekdays and day not in holidays:
            begin = max(instant, opening)
            available = max(
                0,
                (
                    closing.astimezone(timezone.utc) - begin.astimezone(timezone.utc)
                ).total_seconds(),
            )
            if remaining <= available:
                return begin.astimezone(timezone.utc) + timedelta(seconds=remaining)
            remaining -= available
        instant = datetime.combine(day + timedelta(days=1), time(0), zone)
    raise ValueError("Deadline exceeds the bounded business-calendar horizon")
