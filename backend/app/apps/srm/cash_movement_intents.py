"""One native cash movement per durable intent; this module grants no access."""
from hashlib import sha256
import json
from decimal import Decimal
from types import SimpleNamespace
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import inspect, select
from sqlalchemy.orm import object_session

from app.apps.srm.models import SRMPOSCashMovement, SRMPOSSession

FIELDS = ('request_key', 'request_sha256', 'request_currency', 'request_branch_id', 'request_context_id')
_BIRTHS = WeakKeyDictionary()


def fail(message, code=409):
    raise HTTPException(code, message)


def require_schema(db):
    from app.db.schema_columns import table_columns
    columns = table_columns(db.connection(), (SRMPOSCashMovement.__tablename__,))
    if not set(FIELDS) <= columns.get(SRMPOSCashMovement.__tablename__, set()):
        fail('Apply native cash intent migration 119 before using cash registers', 503)
    inspector = inspect(db.connection())
    table = SRMPOSCashMovement.__tablename__
    checks = inspector.get_check_constraints(table)
    unique = inspector.get_unique_constraints(table) + inspector.get_indexes(table)
    if (not any(item['name'] == 'ck_srm_cash_request_source' for item in checks)
            or not any(item['name'] == 'uq_srm_cash_company_request'
                and item['column_names'] == ['organization_id', 'request_key']
                and item.get('unique', True) for item in unique)):
        fail('Native cash intent constraints require migration 119 reconciliation', 503)


def _branch(db, user, session, company, scope):
    from app.branches.models import BranchOwnership, BranchLifecycle
    from app.branches.service import context
    from app.models.company import Branch, Company
    row = db.connection().execute(select(BranchOwnership.branch_id).join(
        Branch, Branch.id == BranchOwnership.branch_id).join(Company, Company.id == Branch.company_id).outerjoin(
        BranchLifecycle, BranchLifecycle.branch_id == Branch.id).where(
            BranchOwnership.resource_table == SRMPOSSession.__tablename__,
            BranchOwnership.resource_key == str(session.id), BranchOwnership.company_id == company,
            Branch.company_id == company, Branch.is_active.is_(True), Company.is_active.is_(True),
            BranchLifecycle.deleted_at.is_(None))).first()
    if row is None:
        fail('Register lacks a verified active native branch; reconcile before recording cash')
    fresh = context(db, user, company, str(row.branch_id))
    bound = db.info.get('branch_context')
    if bound is None or row.branch_id not in bound.writable or row.branch_id not in fresh.writable:
        fail('Current native register branch is not writable', 403)
    if scope is not None and (scope.branch_id != row.branch_id or scope.company_id != company):
        fail('Register does not match its selected business context', 403)
    return row.branch_id, fresh


def _authority(db, user, session, scope, epoch):
    from app.apps.srm.services.commercial import tenant
    from app.business_packs.common_core import _native_authority
    from app.business_packs.access import resolve_context
    from app.business_packs.catalog_management import _module_grant
    from app.access.service import check_background_access
    company = tenant(user)
    if db.info.get('security_write_request') is False or db.info.get('business_pack_scope') != scope:
        fail('Cash intent requires its current native write scope', 403)
    if _native_authority(db, user, company) != epoch:
        fail('Native cash authority changed during the request', 403)
    branch, fresh = _branch(db, user, session, company, scope)
    if resolve_context(db, user, fresh, getattr(scope, 'context_id', None)) != scope:
        fail('Cash intent context changed during the request', 403)
    if scope is not None:
        from app.business_packs.operations import capabilities
        if 'sessions.close' not in capabilities(db, user):
            fail('Assigned business role cannot manage cash drawers', 403)
    check_background_access(db, user, 'srm', 'create', branch_id=branch,
                            administrative_read=False, stamp=False)
    grant = _module_grant(db, user, SimpleNamespace(company_id=company, branch_id=branch), 'srm')
    if not user.is_superuser and (not grant.get('enabled') or 'create' not in grant.get('actions', ())
            or not {'srm_manage', 'srm_admin'}.intersection(grant.get('permissions', ()))):
        fail('Fresh native cash management permission is required', 403)
    return company, branch


def _digest(*, key, company, session, actor, branch, context, currency, movement_type, amount, reason):
    value = {'request_key': key, 'company_id': company, 'session_id': session, 'actor_id': actor,
        'branch_id': branch, 'context_id': context, 'currency': currency, 'movement_type': movement_type,
        'amount': format(Decimal(amount).quantize(Decimal('0.01')), 'f'), 'reason': reason}
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _row_digest(item):
    return _digest(key=item.request_key, company=item.organization_id, session=item.session_id,
        actor=item.created_by, branch=item.request_branch_id, context=item.request_context_id,
        currency=item.request_currency, movement_type=item.movement_type, amount=item.amount, reason=item.reason)


def validate_birth(connection, item):
    db = object_session(item)
    plan = _BIRTHS.get(db) if db is not None else None
    if plan is None or plan[0] is not item or db.connection() is not connection:
        raise ValueError('Cash intent provenance requires the actual native command')
    _, expected, check = plan
    if any(getattr(item, name) != value for name, value in expected.items()):
        raise ValueError('Native cash intent source changed before insertion')
    check()


def _result(db, session, item):
    from app.apps.srm.api.router import _pos_session_summary
    db.refresh(session)
    db.expire(session, ['cash_movements', 'closings'])
    return {**_pos_session_summary(db, session), 'movement_id': item.id, 'request_key': item.request_key}


def create_intent(data, db, user):
    from app.models.user import User
    from app.apps.srm.schemas import SRMPOSCashMovementCreate
    from app.apps.srm.services.commercial import tenant, lock_tenant
    from app.apps.srm.api.router import _get_pos_session, _audit, _serialize
    from app.apps.srm.register_currency import require_cash_currency, evidence
    from app.business_packs.common_core import _native_authority
    if type(data) is not SRMPOSCashMovementCreate or data.request_key is None:
        fail('An actual typed native cash intent is required', 403)
    if type(user) is not User or object_session(user) is not db or not inspect(user).persistent or db in _BIRTHS:
        fail('An authenticated native cash actor is required', 403)
    data = SRMPOSCashMovementCreate.model_validate(data.model_dump())
    require_schema(db)
    company = tenant(user)
    scope = db.info.get('business_pack_scope')
    epoch = _native_authority(db, user, company)
    lock_tenant(db, user)
    session = _get_pos_session(db, data.session_id, user)
    db.refresh(session)

    currency = None
    must_open = False
    must_closed = False

    def check():
        result = _authority(db, user, session, scope, epoch)
        source = db.connection().execute(select(SRMPOSSession.organization_id, SRMPOSSession.status,
            SRMPOSSession.deleted_at).where(SRMPOSSession.id == session.id)).first()
        if source is None or source.organization_id != company or source.deleted_at is not None:
            fail('Native cash register source is unavailable', 404)
        if must_open and source.status != 'open':
            fail('Cannot add cash movement to a closed session', 400)
        if must_closed and source.status != 'closed':
            fail('Cannot add cash movement to a closed session', 400)
        if currency is not None:
            current = evidence(db, session)
            if current['ambiguous'] or current['currency'] != currency:
                fail('Native cash register currency changed or requires reconciliation')
        return result

    _, branch = check()
    currency = require_cash_currency(db, session)
    key = str(data.request_key)
    context = getattr(scope, 'context_id', None)
    digest = _digest(key=key, company=company, session=session.id, actor=user.id, branch=branch,
        context=context, currency=currency, movement_type=data.movement_type, amount=data.amount, reason=data.reason)
    previous = db.query(SRMPOSCashMovement).filter_by(organization_id=company, request_key=key).populate_existing().with_for_update().first()
    if previous is not None:
        if previous.request_sha256 != digest or previous.request_sha256 != _row_digest(previous):
            fail('Cash request key already identifies a different native movement')
        check()
        return _result(db, session, previous)
    # A key hidden by current record/pack authority must never be adopted.
    if db.connection().scalar(select(SRMPOSCashMovement.id).where(
            SRMPOSCashMovement.organization_id == company, SRMPOSCashMovement.request_key == key)) is not None:
        fail('Cash request key is unavailable in the current native scope')
    if session.status != 'open':
        must_closed = True
        check()
        if db.connection().scalar(select(SRMPOSCashMovement.id).where(
                SRMPOSCashMovement.organization_id == company, SRMPOSCashMovement.request_key == key)) is not None:
            fail('Cash request key is unavailable in the current native scope')
        check()
        raise HTTPException(400, 'Cannot add cash movement to a closed session', headers={
            'X-Cash-Intent-Outcome': 'not_created', 'X-Cash-Intent-Request-Key': key,
            'X-Cash-Intent-Session-Id': str(session.id)})
    must_open = True
    item = SRMPOSCashMovement(organization_id=company, session_id=session.id, created_by=user.id,
        movement_type=data.movement_type, amount=data.amount, reason=data.reason,
        request_key=key, request_sha256=digest, request_currency=currency,
        request_branch_id=branch, request_context_id=context)
    expected = {column.name: getattr(item, column.name) for column in item.__table__.columns
                if column.name not in {'id', 'created_at'}}
    _BIRTHS[db] = (item, expected, check)
    try:
        db.add(item); db.flush()
        from app.apps.srm.api.router import _pos_session_summary
        session.expected_cash = _pos_session_summary(db, session)['expected_cash']
        _audit(db, user, 'pos_cash_movement', item.id, 'created', after=_serialize(item))
        check()
        db.commit()
    finally:
        _BIRTHS.pop(db, None)
    check()
    return _result(db, session, item)
