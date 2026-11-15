"""Narrow server-owned materializations emitted by authorized payroll reads.

This marker never changes the actor's branch context or permits arbitrary business
writes. The branch boundary still verifies native parent ownership on each row.
"""
from contextlib import contextmanager


@contextmanager
def chat_read_derivatives(db, workspace_id: int):
    """Allow only canonical legacy-chat copies in one authorized workspace.

    The caller first checks workspace membership. Every new row must still
    resolve to a single writable native branch in the boundary listener.
    """
    from fastapi import HTTPException
    from app.apps.project_management.chat_models import ChatConversation
    previous = db.info.get('derived_read_parents')
    allowed = dict(previous or {})
    table = 'pms_chat_conversations'
    allowed[table] = frozenset(allowed.get(table, ())) | {workspace_id}
    db.info['derived_read_parents'] = allowed

    def allow_room(room_id):
        room = db.get(ChatConversation, room_id)
        if room is None or room.workspace_id != workspace_id:
            raise HTTPException(403, 'Chat materialization source is outside the workspace')
        for name in ('pms_chat_members', 'pms_chat_messages'):
            allowed[name] = frozenset(allowed.get(name, ())) | {room_id}

    try:
        yield allow_room
    finally:
        if previous is None:
            db.info.pop('derived_read_parents', None)
        else:
            db.info['derived_read_parents'] = previous


@contextmanager
def profitability_read_derivatives(db, engagement_id: int):
    previous = db.info.get('derived_read_parents')
    allowed = dict(previous or {})
    table = 'srm_profitability_snapshots'
    allowed[table] = frozenset(allowed.get(table, ())) | {engagement_id}
    db.info['derived_read_parents'] = allowed
    try:
        yield
    finally:
        if previous is None:
            db.info.pop('derived_read_parents', None)
        else:
            db.info['derived_read_parents'] = previous


@contextmanager
def payroll_read_derivatives(db, run_id: int, *, variance=False, download=False):
    tables = set()
    if variance:
        tables.add('payroll_variance_items')
    if download:
        tables.add('payroll_run_audit_logs')
    previous = db.info.get('derived_read_parents')
    allowed = dict(previous or {})
    for table in tables:
        allowed[table] = frozenset(allowed.get(table, ())) | {run_id}
    db.info['derived_read_parents'] = allowed
    try:
        yield
    finally:
        if previous is None:
            db.info.pop('derived_read_parents', None)
        else:
            db.info['derived_read_parents'] = previous
