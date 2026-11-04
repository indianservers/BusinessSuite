"""Signed, scope-bound keyset paging over bounded native ORM source queries."""
import base64
import hashlib
import hmac
import json
from datetime import date as DateValue, datetime, timezone
from fastapi import HTTPException
from sqlalchemy import DateTime, String, cast, literal, func, or_, and_
from app.core.config import settings
from app.apps.srm.services.commercial import tenant


def scope_key(db, user, filters):
    branch = db.info.get('branch_context')
    scope = [tenant(user), user.id, getattr(branch, 'branch_id', None), sorted(getattr(branch, 'allowed', []) or []), filters]
    return hashlib.sha256(json.dumps(scope, sort_keys=True, default=str).encode()).hexdigest()


def encode_cursor(data):
    body = base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':'), sort_keys=True).encode()).decode().rstrip('=')
    signature = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + '.' + signature


def decode_cursor(value, scope):
    try:
        if not isinstance(value, str) or len(value) > 8192:
            raise ValueError()
        body, signature = value.split('.')
        expected = hmac.new(settings.SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(body + '=' * (-len(body) % 4)))
        if data['scope'] != scope or data['v'] != 2 or len(data['last']) != 4 or not isinstance(data['last'][2], int):
            raise ValueError()
        return data
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(422, 'Invalid cursor or cursor from another record, branch or filter')


def bounded_page(sources, *, scope, cursor=None, page=1, per_page=25, descending=False, snapshot=False, include_total=True):
    """Merge at most (page-size + 1) rows per source. No dataset-sized ORM list."""
    state = decode_cursor(cursor, scope) if cursor else {'v': 2, 'scope': scope, 'last': None, 'watermarks': {}}
    if snapshot and not cursor:
        for prefix, query, date, key in sources:
            state['watermarks'][prefix] = query.order_by(None).with_entities(func.max(key)).scalar() or 0
    prepared = []
    total = 0 if include_total else None
    for prefix, query, date, key in sources:
        if snapshot:
            query = query.filter(key <= state['watermarks'].get(prefix, 0))
        if include_total:
            total += query.order_by(None).count()
        prepared.append((prefix, query, date, key))
    result, has_more = [], False
    # Legacy numbered callers stay compatible using bounded batches. The UI uses
    # cursors, so later pages never rescan the preceding history/work rows.
    requested = 1 if cursor else page
    for index in range(requested):
        candidates = []
        for prefix, query, date, key in prepared:
            last = state['last']
            if last:
                stamp, source, identity, raw = last
                tie = (key < identity if descending else key > identity) if prefix == source else (prefix < source if descending else prefix > source)
                if stamp in ('', '9999'):
                    condition = and_(date.is_(None), tie)
                else:
                    current_datetime = isinstance(date.type, DateTime)
                    last_datetime = len(stamp) > 10
                    boundary = datetime.fromisoformat(stamp) if last_datetime else DateValue.fromisoformat(stamp)
                    if current_datetime:
                        if not last_datetime:
                            boundary = datetime.combine(boundary, datetime.min.time(), timezone.utc)
                        if not getattr(date.type, 'timezone', False):
                            boundary = boundary.replace(tzinfo=None)
                    elif last_datetime:
                        boundary = boundary.date()
                    if current_datetime != last_datetime:
                        if current_datetime and query.session.get_bind().dialect.name == 'sqlite':
                            boundary = literal(stamp + ' 00:00:00', type_=String())
                        # A calendar date sorts before timed work on that date.
                        condition = (date < boundary if current_datetime else date <= boundary) if descending else (date >= boundary if current_datetime else date > boundary)
                    else:
                        if current_datetime and query.session.get_bind().dialect.name == 'sqlite':
                            # SQLite can store server timestamps without '.000000'.
                            # Compare the exact stored key, not a reformatted bind
                            # that would put the same event on two adjacent pages.
                            boundary = literal(raw, type_=String())
                        condition = or_(date < boundary if descending else date > boundary, and_(date == boundary, tie))
                    condition = or_(condition, date.is_(None))
                query = query.filter(condition)
            # Keep native date columns in ordering/range predicates so existing
            # due-date/event indexes remain usable; never CAST the indexed key.
            order = [date.desc().nulls_last(), key.desc()] if descending else [date.asc().nulls_last(), key.asc()]
            for row, value, raw in query.order_by(None).add_columns(date.label('_feed_sort'), cast(date, String).label('_feed_raw')).order_by(*order).limit(per_page + 1):
                stamp = raw.replace(' ', 'T') if raw is not None and query.session.get_bind().dialect.name == 'sqlite' else (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat(timespec='microseconds') if isinstance(value, datetime) else value.isoformat() if value is not None else '' if descending else '9999'
                candidates.append((stamp, prefix, row.id, row, raw))
        candidates.sort(key=lambda value: value[:3], reverse=descending)
        result = candidates[:per_page]
        has_more = len(candidates) > per_page
        if result:
            state['last'] = [*result[-1][:3], result[-1][4]]
        if not has_more:
            if index < requested - 1:
                result = []
            break
    return {'rows': [row[:4] for row in result], 'total': total, 'has_more': has_more, 'next_cursor': encode_cursor(state) if has_more else None}
