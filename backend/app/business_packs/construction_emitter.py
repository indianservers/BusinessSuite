"""Opaque, factory-issued Construction emitter attestation.

No query/session API is conferred by a frame. Its verifier reuses the exact
factory's existing guard and native-authority fingerprint.
"""
from dataclasses import dataclass
from sys import _getframe
from weakref import WeakKeyDictionary, WeakSet, ref

from fastapi import HTTPException
from sqlalchemy import event, inspect

from app.models.user import User
from app.business_packs.access import PackScope
from app.business_packs.boundary import _current
from app.business_packs.common_core import _native_authority
from app.business_packs import construction_planning as _planning
from app.business_packs import construction_definition as _definition
from app.business_packs import construction_workspace_members as _members

# Capture real code AND globals once, never resolve a caller-supplied function
# or consult mutable marker attributes to issue authority. Compare code by is.
_PLANNING = (_planning._run.__code__, _planning._run.__globals__)
_DEFINITION = (_definition._native.__code__, _definition._native.__globals__)
_MEMBERS = (_members._native.__code__, _members._native.__globals__)
_BIRTH_TYPE = _definition._Birth
_BIRTH_CURRENT = _definition._Birth.current
_MEMBER_TYPE = _members._Member
_MEMBER_CURRENT = _members._Member.current
_ISSUED = WeakSet()
_FACTS = WeakKeyDictionary()
_RETAINED = WeakKeyDictionary()
_WATCHED = WeakSet()


def _deny():
    raise HTTPException(403, 'A genuine current Construction emitter frame is required')


class _Frame:
    __slots__ = ('__weakref__',)

    def __new__(cls):
        _deny()


@dataclass(eq=False)
class _Facts:
    native: object
    parent: object
    actor: object
    self_user: object
    scope: object
    scope_key: tuple
    root_transaction: object
    owned_savepoint: object
    native_transaction: object
    purpose: str
    epoch: str
    current: object
    active: bool = True
    sealed: bool = False


def _scope_key(scope):
    return (scope.company_id, scope.branch_id, scope.context_id, scope.activation_id,
        scope.pack_key, scope.pack_version, scope.user_id, scope.grant_id, scope.role,
        scope.capabilities, scope.writable, scope.revisions)


def _factory(caller):
    if caller.f_code is _PLANNING[0] and caller.f_globals is _PLANNING[1]:
        return 'planning'
    if caller.f_code is _DEFINITION[0] and caller.f_globals is _DEFINITION[1]:
        return 'definition'
    if caller.f_code is _MEMBERS[0] and caller.f_globals is _MEMBERS[1]:
        return 'member'
    _deny()


def _facts(frame):
    if type(frame) is not _Frame or frame not in _ISSUED or frame not in _FACTS:
        _deny()
    return _FACTS[frame]


def _parent_current(facts):
    parent, actor = facts.parent(), facts.actor()
    state = inspect(actor, raiseerr=False)
    root = facts.root_transaction()
    if (parent is None or root is None or not root.is_active or parent.get_transaction() is not root
            or type(actor) is not User or state is None or not state.persistent or state.session is not parent
            or state.obj() is not actor or parent.identity_map.get(state.key) is not actor
            or state.identity != (facts.scope.user_id,)
            or parent.info.get('business_pack_scope') is not facts.scope
            or _scope_key(facts.scope) != facts.scope_key):
        _deny()
    _current(facts.scope, parent.connection())
    if _native_authority(parent, actor, facts.scope.company_id) != facts.epoch:
        _deny()
    facts.current()  # exact captured existing factory guard, never caller code
    return parent


def _active_current(facts, native, scope, parent):
    if (not facts.active or native is not facts.native() or parent is not facts.parent()
            or scope is not facts.scope):
        _deny()
    _parent_current(facts)
    user_state = inspect(facts.self_user, raiseerr=False)
    transaction = facts.native_transaction()
    savepoint = facts.owned_savepoint()
    if (type(facts.self_user) is not User or user_state is None or not user_state.persistent
            or user_state.session is not native or user_state.identity != (scope.user_id,)
            or user_state.obj() is not facts.self_user or native.identity_map.get(user_state.key) is not facts.self_user
            or transaction is None or not transaction.is_active or native.get_transaction() is not transaction
            or savepoint is None or not savepoint.is_active or parent.get_nested_transaction() is not savepoint
            or native.info.get('shared_actor') != (scope.user_id, scope.company_id)):
        _deny()


def _watch(parent):
    if parent in _WATCHED:
        return
    _WATCHED.add(parent)
    def before_commit(session):
        # Nested owned-savepoint release is NOT the caller's root commit.
        if session.get_nested_transaction() is None:
            for frame in tuple(_RETAINED.get(session, ())):
                facts = _facts(frame)
                if not facts.sealed:
                    _deny()
                _parent_current(facts)
    def ended(session, transaction):
        if transaction.parent is None:
            for frame in tuple(_RETAINED.pop(session, ())):
                _ISSUED.discard(frame)
                _FACTS.pop(frame, None)
    event.listen(parent, 'before_commit', before_commit)
    event.listen(parent, 'after_transaction_end', ended)


def issue(native, *, parent, scope, actor, self_user, purpose, current, epoch):
    caller = _getframe(1)
    factory = _factory(caller)
    local = caller.f_locals
    if (local.get('reader' if factory == 'member' else 'native') is not native or local.get('db') is not parent
            or local.get('scope') is not scope or local.get('actor') is not actor
            or local.get('principal') is not self_user):
        _deny()
    if factory == 'planning':
        action = local.get('action')
        expected = {'apply': 'construction.schedule.apply', 'capture': 'construction.schedule.capture',
            'task_actual': 'construction.actuals.task', 'cost_actual': 'construction.actuals.cost',
            'cost_budget': 'construction.actuals.budget'}.get(action)
        if expected is None or purpose != expected or current is not local.get('current') or epoch != local.get('authority'):
            _deny()
    elif factory == 'definition':
        plan = local.get('plan')
        if (type(plan) is not _BIRTH_TYPE or getattr(current, '__self__', None) is not plan
                or getattr(current, '__func__', None) is not _BIRTH_CURRENT
                or purpose != {'project_definition': 'construction.definition.project',
                    'task_definition': 'construction.definition.task'}.get(plan.kind) or epoch != plan.authority):
            _deny()
    else:
        plan = local.get('plan')
        if (type(plan) is not _MEMBER_TYPE or getattr(current, '__self__', None) is not plan
                or getattr(current, '__func__', None) is not _MEMBER_CURRENT
                or purpose != 'construction.team.member' or epoch != plan.authority):
            _deny()
    if (not isinstance(scope, PackScope) or scope.pack_key != 'construction' or parent is native
            or type(actor) is not User or type(self_user) is not User or not isinstance(epoch, str)):
        _deny()
    root, savepoint, native_transaction = parent.get_transaction(), parent.get_nested_transaction(), native.get_transaction()
    if root is None or savepoint is None or native_transaction is None:
        _deny()
    frame = object.__new__(_Frame)
    facts = _Facts(ref(native), ref(parent), ref(actor), self_user, scope, _scope_key(scope),
        ref(root), ref(savepoint), ref(native_transaction), purpose, epoch, current)
    _FACTS[frame] = facts
    _ISSUED.add(frame)
    try:
        _active_current(facts, native, scope, parent)
        _watch(parent)
    except Exception:
        _FACTS.pop(frame, None)
        _ISSUED.discard(frame)
        raise
    return frame


def verify_native_emitter(native, scope, *, parent, frame):
    """Common bind_native_emitter callback: Boolean proof, no returned authority."""
    try:
        _active_current(_facts(frame), native, scope, parent)
        return True
    except (HTTPException, AttributeError, TypeError, ValueError):
        return False


def seal(frame):
    # Must run in the exact successful factory, after all validated native
    # births/anchors/certificates and final output proofs, BEFORE native commit.
    caller = _getframe(1)
    factory = _factory(caller)
    facts = _facts(frame)
    if facts.sealed:
        _deny()
    native, parent = facts.native(), facts.parent()
    if caller.f_locals.get('reader' if factory == 'member' else 'native') is not native or caller.f_locals.get('db') is not parent:
        _deny()
    _active_current(facts, native, facts.scope, parent)
    facts.sealed = True
    _RETAINED.setdefault(parent, set()).add(frame)


def release_native(frame, *, successful):
    # finally: common unbind first; release only this native binding. A sealed
    # success survives commit=False and savepoint release until the ROOT ends.
    caller = _getframe(1)
    factory = _factory(caller)
    facts = _facts(frame)
    if caller.f_locals.get('reader' if factory == 'member' else 'native') is not facts.native() or caller.f_locals.get('db') is not facts.parent():
        _deny()
    facts.active = False
    if not successful or not facts.sealed:
        parent = facts.parent()
        if parent in _RETAINED:
            _RETAINED[parent].discard(frame)
        _FACTS.pop(frame, None)
        _ISSUED.discard(frame)
