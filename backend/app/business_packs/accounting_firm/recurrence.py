"""Bounded, explicit recurring periods; no scheduler or implicit worked hours."""
from calendar import monthrange
from datetime import date
from uuid import uuid5

from . import service
from .models import AccountsCommand


def shift_month(value, months):
    """Anchor every occurrence to the original day, preserving month ends."""
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    if not 1 <= year <= 9999:
        service.fail('Recurring period exceeds the supported calendar', 422)
    last = monthrange(year, month)[1]
    day = last if value.day == monthrange(value.year, value.month)[1] else min(value.day, last)
    return date(year, month, day)


def create_series(data, db, actor, *, commit=True):
    scope = service.authority(db, actor, 'engagements.manage', write=True)
    service.lock_tenant(db, actor)
    service.authority(db, actor, 'engagements.manage', write=True)
    service.source(db, actor, scope, data.engagement_id, data.client_id)
    service.staff(db, scope, data.preparer_employee_id, data.reviewer_employee_id)
    old = service.replay(db, actor, scope, 'create', None, data)
    if old is not None:
        return old
    service.source(db, actor, scope, data.engagement_id, data.client_id, require_open=True)
    # Validate all calendar values before beginning any writes.
    inputs = []
    for index in range(data.occurrences):
        months = index * data.interval_months
        values = data.model_dump() | {'occurrences': 1,
            'request_key': uuid5(data.request_key, f'accounts-period:{index}'),
            **{key: shift_month(getattr(data, key), months)
               for key in ('starts_on', 'ends_on', 'due_on')}}
        inputs.append(type(data).model_validate(values))
    with db.begin_nested():
        periods = [service.create(item, db, actor, commit=False) for item in inputs]
        result = dict(periods[0], periods=periods)
        db.add(AccountsCommand(**service.fields(scope, actor), period_id=periods[0]['id'],
            request_key=str(data.request_key), request_sha256=service.fingerprint('create', None, data),
            action='create', reason='', result=result))
        db.flush()
    if commit:
        db.commit()
    return result
