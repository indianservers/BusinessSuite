"""Deduplicate approved leave intervals without choosing a calendar policy."""
from datetime import timedelta


def add_leave_intervals(target, leave, period_start, period_end):
    if getattr(leave, 'deleted_at', None) is not None or leave.status != 'Approved':
        return
    cursor=max(leave.from_date,period_start)
    end=min(leave.to_date,period_end)
    while cursor<=end:
        slots={0,1}
        if leave.is_half_day:
            part=(leave.half_day_period or 'First Half').strip().lower().replace('_',' ')
            slots={1 if part=='second half' else 0}
        target.setdefault(cursor,set()).update(slots)
        if leave.is_half_day:break
        cursor+=timedelta(days=1)
