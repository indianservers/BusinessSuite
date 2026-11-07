"""Opt-in, authorization-first synchronization of bounded record views.

Snapshots contain hashes, not records. Every check executes the original route;
there is no cached authorization decision or second, less restricted data API.
Worker restart/eviction produces a full reset, never an incomplete delta.
"""
from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
import json
import re
import secrets
import time
from threading import Lock
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

MAX_ROWS = 500
MAX_BODY = 2 * 1024 * 1024
TTL = 900
# Explicit collection endpoints only. Financial/attendance views remain memory-only.
PERSIST = re.compile(r"^/api/v1/(?:project-management/(?:projects|tasks|teams|people-workspace/people|people-workspace/groups)|crm/(?:leads|lead-management/leads|contact-directory|contacts|accounts|companies|deals|deal-workspace/(?:query|grid/query)|customers|products|services)|srm/(?:customers|products|services)|catalog/(?:products|services|items)|profiles/directory|employees(?:/directory)?|departments|teams|company/(?:departments|teams)|interns-hub/(?:management/batches|learning/assignments))/?$")
MEMORY = re.compile(r"^/api/v1/(?:master-data/(?:companies|contacts|company-directory/query)|crm/(?:quotes|quotations|sales-orders)|srm/(?:sales-orders|sales|quotations|customer-360)|attendance/(?:my|team|register)|leave/(?:requests|my|my-requests))/?$")
SENSITIVE = re.compile(r"password|token|secret|bank|iban|aadhaar|aadhar|pan_?number|passport|national_?id|ssn|tax_?id|home_?address|emergency_?contact|salary(?!_currency)|compensation|payroll|document|personal_?email|date_?of_?birth|dob(?:$|_)|medical|biometric|latitude|longitude", re.I)

def eligible(path):
    return bool(PERSIST.fullmatch(path) or MEMORY.fullmatch(path))

def sensitive(value):
    if isinstance(value, dict):
        return any((SENSITIVE.search(str(k)) and v not in (None, '', [], {})) or sensitive(v) for k, v in value.items())
    if isinstance(value, str):
        return bool(re.search(r'(?:[?&](?:token|access_token|api_key|signature)=|X-Amz-Signature=)', value, re.I))
    return isinstance(value, list) and any(sensitive(v) for v in value)

def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def row_id(row):
    if not isinstance(row, dict):
        return None
    if 'task_id' in row and 'user_id' in row and 'id' not in row:
        return f"task:{row['task_id']}:user:{row['user_id']}" if all(isinstance(row[k], (int, str)) and not isinstance(row[k], bool) for k in ('task_id', 'user_id')) else None
    if 'attendance_id' in row and isinstance(row.get('employee_id'), (int, str)) and isinstance(row.get('date'), str):
        return f"employee:{row['employee_id']}:date:{row['date']}"
    if row.get('kind') in ('product', 'service') and isinstance(row.get('id'), (int, str)) and not isinstance(row.get('id'), bool):
        return f"{row['kind']}:{row['id']}"
    value = row.get('id', row.get('userId'))
    return str(value) if isinstance(value, (int, str)) and not isinstance(value, bool) else None

def split_view(payload):
    key = None if isinstance(payload, list) else next((k for k in ('items', 'results', 'records', 'rows') if isinstance(payload, dict) and isinstance(payload.get(k), list)), None)
    rows = payload if isinstance(payload, list) else payload.get(key) if key else None
    if rows is None or len(rows) > MAX_ROWS:
        return None
    ids = [row_id(row) for row in rows]
    if None in ids or len(set(ids)) != len(ids):
        return None
    return key, rows, ids, {} if key is None else {k: v for k, v in payload.items() if k != key}

@dataclass
class Snapshot:
    scope: str
    etag: str
    hashes: dict
    key: str | None
    expires: float

class SnapshotStore:
    def __init__(self, capacity=256):
        self.capacity = capacity
        self.entries = OrderedDict()
        self.lock = Lock()

    def get(self, cursor, scope):
        with self.lock:
            entry = self.entries.get(cursor)
            if entry and entry.scope == scope and entry.expires > time.monotonic():
                return entry
        return None

    def put(self, entry):
        cursor = secrets.token_urlsafe(24)
        with self.lock:
            self.entries[cursor] = entry
            while len(self.entries) > self.capacity:
                self.entries.popitem(last=False)
        return cursor

class RecordSyncMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, store=None):
        super().__init__(app)
        self.store = store or SnapshotStore()

    async def dispatch(self, request, call_next):
        # A client without the negotiated protocol receives the original API.
        requested = request.method == 'GET' and request.headers.get('x-suite-sync') == '1' and eligible(request.url.path)
        response = await call_next(request)
        actor_scope = getattr(request.state, 'record_sync_scope', None)
        if not requested or not actor_scope or response.status_code != 200 or 'application/json' not in response.headers.get('content-type', '') or response.headers.get('content-encoding') or 'no-store' in response.headers.get('cache-control', '').lower():
            return response
        body = b''.join([chunk async for chunk in response.body_iterator])
        headers = dict(response.headers)
        headers.pop('content-length', None)
        def original():
            return Response(body, status_code=200, headers=headers, background=response.background)
        if len(body) > MAX_BODY:
            return original()
        try:
            payload = json.loads(body)
            view = split_view(payload)
        except (ValueError, TypeError):
            return original()
        if not view or sensitive(payload):
            return original()
        key, rows, order, meta = view
        scope = digest([actor_scope, request.url.path, sorted(request.query_params.multi_items())])
        etag = '"' + digest(payload) + '"'
        previous = self.store.get(request.headers.get('x-suite-sync-cursor'), scope)
        hashes = {i: digest(row) for i, row in zip(order, rows)}
        cursor = self.store.put(Snapshot(scope, etag, hashes, key, time.monotonic() + TTL))
        headers.update({'ETag': etag, 'X-Suite-Sync-Cursor': cursor, 'X-Suite-Sync-Scope': actor_scope, 'X-Suite-Sync-Mode': 'full', 'X-Suite-Cache': 'persist' if PERSIST.fullmatch(request.url.path) else 'memory', 'Cache-Control': 'private, max-age=0, must-revalidate', 'Vary': 'Authorization, X-Suite-Organization, X-Suite-Branch, X-Suite-Sync, X-Suite-Sync-Cursor'})
        request.state.record_sync_cacheable = True
        # An HTTP cache may add If-None-Match after the JS baseline was lost.
        # Its cached body can be a delta, so 304 is safe only with a live,
        # matching protocol cursor. Otherwise return the full representation.
        if previous and previous.key == key and request.headers.get('if-none-match') == etag:
            headers['X-Suite-Sync-Mode'] = 'unchanged'
            return Response(status_code=304, headers=headers, background=response.background)
        if previous and previous.key == key:
            delta = {'schema': 1, 'key': key, 'order': order, 'upserts': [row for i, row in zip(order, rows) if previous.hashes.get(i) != hashes[i]], 'removed': sorted(set(previous.hashes) - set(order)), 'meta': meta}
            encoded = json.dumps(delta, separators=(',', ':'), ensure_ascii=False).encode()
            if len(encoded) < len(body):
                headers['X-Suite-Sync-Mode'] = 'delta'
                return Response(encoded, media_type='application/json', headers=headers, background=response.background)
        return original()
