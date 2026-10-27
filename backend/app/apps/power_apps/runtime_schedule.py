"""Calendar schedules in UTC, with explicit skip-gap / first-fold DST semantics."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from app.apps.power_apps.runtime_contracts import ScheduleConfig

UTC = timezone.utc


def aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("Schedule timestamps must include a timezone")
    return value.astimezone(UTC)


def cron_fields(expression):
    fields = expression.split()
    if len(fields) != 5:
        raise ValueError("Cron requires five numeric fields")
    result = []
    for raw, lo, hi in zip(fields, [0, 0, 1, 1, 0], [59, 23, 31, 12, 6]):
        values = set()
        for section in raw.split(","):
            base, *step = section.split("/")
            if len(step) > 1 or (
                step and (not step[0].isdigit() or not 1 <= int(step[0]) <= 60)
            ):
                raise ValueError("Invalid cron step")
            stride = int(step[0]) if step else 1
            if base == "*":
                start, end = lo, hi
            elif "-" in base:
                parts = base.split("-")
                if len(parts) != 2 or not all(v.isdigit() for v in parts):
                    raise ValueError("Invalid cron range")
                start, end = map(int, parts)
            elif base.isdigit():
                start = end = int(base)
            else:
                raise ValueError(
                    "Cron supports numeric ranges, lists, wildcards and steps"
                )
            if not lo <= start <= end <= hi:
                raise ValueError("Cron field outside bounds")
            values.update(range(start, end + 1, stride))
        result.append(values)
    return result, fields


def next_occurrence(config, after):
    c = ScheduleConfig.model_validate(config)
    tz = ZoneInfo(c.timezone)
    after = aware(after)
    start = aware(c.start_at)
    end = aware(c.end_at)
    if start and end and start > end:
        raise ValueError("Schedule start exceeds end")
    if c.mode == "once":
        if not c.at:
            raise ValueError("One-time schedule requires at")
        candidate = aware(c.at)
        return (
            candidate
            if candidate > after
            and (not start or candidate >= start)
            and (not end or candidate <= end)
            else None
        )
    lower = max(after, start - timedelta(microseconds=1)) if start else after
    if c.mode == "minutes":
        anchor = start or datetime(2020, 1, 1, tzinfo=UTC)
        span = timedelta(minutes=c.every_minutes)
        candidate = anchor + max(0, (lower - anchor) // span + 1) * span
        return candidate if not end or candidate <= end else None
    expression = (
        c.cron
        if c.mode == "cron"
        else f"{c.minute} "
        + (
            "* * * *"
            if c.mode == "hourly"
            else (
                f"{c.hour} * * *"
                if c.mode == "daily"
                else (
                    f"{c.hour} * * {(c.weekday+1)%7}"
                    if c.mode == "weekly"
                    else f"{c.hour} {c.day} * *"
                )
            )
        )
    )
    values, raw = cron_fields(expression)
    # Enumerate local dates and allowed hours/minutes rather than scanning every UTC minute.
    first = lower.astimezone(tz).date()
    candidates = []
    for offset in range(366 * 5):
        day = first + timedelta(days=offset)
        if day.month not in values[3]:
            continue
        dom = day.day in values[2]
        dow = (day.weekday() + 1) % 7 in values[4]
        date_match = (
            (dom or dow)
            if not raw[2].startswith("*") and not raw[4].startswith("*")
            else dom and dow
        )
        if not date_match:
            continue
        for hour in sorted(values[1]):
            for minute in sorted(values[0]):
                local = datetime(
                    day.year, day.month, day.day, hour, minute, tzinfo=tz, fold=0
                )
                candidate = local.astimezone(UTC)
                if candidate.astimezone(tz).replace(tzinfo=None) != local.replace(
                    tzinfo=None
                ):
                    continue  # nonexistent local time
                if candidate > lower and (not end or candidate <= end):
                    candidates.append(candidate)
        if candidates:
            return min(candidates)
        if (
            end
            and datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(UTC) > end
        ):
            return None
    raise ValueError("No schedule occurrence within five years")
