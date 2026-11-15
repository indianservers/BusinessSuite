"""Exact newborn-only canonical identity graph for counter-account setup.

Boundary adapters must retain all native tenant, branch and field guards. These
hooks grant neither existing-customer adoption nor arbitrary CRM model access.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from weakref import WeakKeyDictionary
import json

from sqlalchemy import false, inspect, select, func
from fastapi import HTTPException

from . import anonymous_definitions as definitions

_active = WeakKeyDictionary()


def _deny():
    raise HTTPException(403, 'Anonymous canonical account birth is outside its certified graph')


def _models():
    from app.apps.crm.models import CRMCompany, CRMContact
    from app.apps.crm.contact_identity import ContactIdentityLink
    from app.shared.master_data_models import CompanyMasterDetails, BusinessRelationship
    from app.models.audit import AuditLog
    return CRMCompany, CRMContact, ContactIdentityLink, CompanyMasterDetails, BusinessRelationship, AuditLog


def _read_models():
    from app.shared.master_data_models import ContactChannel
    from app.apps.srm.commercial_models import CustomerLink
    return (*_models(), ContactChannel, CustomerLink)


@dataclass
class _Birth:
    actor: object
    payload: object
    scope: object
    company: int
    branch: int
    root: object = None
    objects: dict = field(default_factory=dict)
    checking: bool = False


def _current(db):
    state = _active.get(db)
    if state is not None:
        if db.info.get('business_pack_scope') is not state.scope:
            _deny()
        lease = definitions._leases.get(db)
        if (lease is None or lease.actor is not state.actor or lease.payload is not state.payload
                or definitions._input(state.payload) != lease.snapshot):
            _deny()
    return state


@contextmanager
def canonical_account_birth(db, actor, payload):
    if db in _active:
        _deny()
    with definitions.anonymous_company_birth(db, actor, payload):
        lease = definitions._leases[db]
        # The canonical writer applies this same normalized-name check. Its
        # ordinary ORM query cannot inspect existing bodies inside this closed
        # newborn graph, so retain the check as a blind, company-bound EXISTS.
        company = _models()[0].__table__
        collision = select(company.c.id).where(
            company.c.organization_id == lease.company,
            company.c.deleted_at.is_(None),
            func.lower(func.trim(company.c.name)) == payload.name.casefold()).exists()
        if db.connection().scalar(select(collision)):
            raise HTTPException(409, 'A company with this name already exists; use a distinct counter account label')
        state = _Birth(actor, payload, db.info.get('business_pack_scope'), lease.company, lease.branch)
        _active[db] = state
        try:
            yield
            definitions.assert_company_birth_input(db, actor, 'srm', payload, None)
            if state.root is None:
                _deny()
            for item in tuple(state.objects.values()):
                if not allow_write(db, item):
                    _deny()
        finally:
            if _active.get(db) is state:
                del _active[db]
            # A temporary creation lease must not leave intrinsic private
            # identity bodies readable from this Session's identity map.
            for item in tuple(state.objects.values()):
                native = inspect(item)
                if native.session is db and native.persistent:
                    db.expire(item)


def leased_models(db):
    return _read_models() if _current(db) is not None else ()


def prepare_flush(db):
    """Certify canonical pending parents before a boundary visits children."""
    if _current(db) is None:
        return
    for model in _models():
        candidates = [item for item in db.new if type(item) is model]
        if len(candidates) > 1:
            _deny()
        for item in candidates:
            allow_write(db, item)


def read_criteria(db):
    """Only actual objects born in this lease; never a caller-supplied ID."""
    state = _current(db)
    if state is None:
        return {}
    output = {}
    for model in _read_models():
        item = state.objects.get(model)
        native = inspect(item) if item is not None else None
        if native is None or not native.persistent or native.session is not db:
            output[model] = false()
        else:
            output[model] = next(iter(model.__table__.primary_key)) == native.identity[0]
    return output


def _only(item, expected, *, optional=None):
    optional = optional or {}
    values = inspect(item).dict
    for column in item.__table__.c:
        key = column.key
        value = values.get(key)
        if key in expected:
            if value != expected[key]:
                _deny()
        elif key in optional:
            if value not in optional[key]:
                _deny()
        elif key in {'id', 'created_at', 'updated_at'}:
            continue
        elif value not in (None, '', [], {}):
            _deny()


def allow_write(db, item):
    state = _current(db)
    if state is None or type(item) not in _models():
        return False
    native = inspect(item)
    if native.session is not db or native.deleted or item in db.deleted:
        _deny()
    known = state.objects.get(type(item))
    if known is not None and known is not item:
        _deny()
    if known is None and (not native.pending or native.identity is not None):
        _deny()
    if known is None and type(item) is not _models()[3] and native.dict.get('id') is not None:
        _deny()
    if native.persistent and any(native.dict.get(column.key) != value
            for column, value in zip(native.mapper.primary_key, native.identity)):
        _deny()
    if not state.checking:
        state.checking = True
        try:
            definitions.assert_company_birth_input(db, state.actor, 'srm', state.payload, None)
        finally:
            state.checking = False
    company, contact, link, details, relationship, audit = _models()
    root = state.root
    if type(item) is company:
        if root is not None and root is not item:
            _deny()
        _only(item, {'organization_id': state.company, 'name': state.payload.name,
                    'owner_user_id': state.actor.id, 'created_by_user_id': state.actor.id},
              optional={'branch_id': (None, state.branch), 'country': (None, 'India', state.payload.country),
                        'account_type': (None, 'Prospect', 'Customer'), 'status': (None, 'Active'),
                        'tags_text': (None, ''), 'notes': (None, state.payload.notes),
                        'updated_by_user_id': (None, state.actor.id)})
        state.root = root = item
    elif root is None:
        _deny()
    elif type(item) is contact:
        if native.pending and native.dict.get('company') is not root:
            _deny()
        if native.persistent and native.dict.get('company_id') != root.id:
            _deny()
        _only(item, {'organization_id': state.company, 'full_name': state.payload.name,
                    'first_name': state.payload.name.split(' ', 1)[0][:100],
                    'owner_user_id': state.actor.id, 'created_by_user_id': state.actor.id},
              optional={'company_id': (None, root.id), 'branch_id': (None, state.branch),
                        'status': (None, 'Active'), 'lifecycle_stage': (None, 'Prospect', 'Customer'),
                        'tags_text': (None, 'Prospect', 'Customer'), 'country': (None, 'India')})
    elif type(item) is link:
        born_contact = state.objects.get(contact)
        if born_contact is None or (native.pending and (native.dict.get('account') is not root
                or native.dict.get('contact') is not born_contact)):
            _deny()
        if native.persistent and (native.dict.get('account_id'), native.dict.get('contact_id')) != (root.id, born_contact.id):
            _deny()
        _only(item, {'organization_id': state.company}, optional={
            'account_id': (None, root.id), 'contact_id': (None, born_contact.id)})
    elif type(item) is details:
        if not inspect(root).persistent or item.account_id != root.id:
            _deny()
        _only(item, {'account_id': root.id, 'organization_id': state.company},
              optional={'addresses': (None, []), 'tax_registrations': (None, []), 'version': (None, 1)})
    elif type(item) is relationship:
        if not inspect(root).persistent:
            _deny()
        _only(item, {'account_id': root.id, 'organization_id': state.company, 'role': 'Customer'},
              optional={'status': (None, 'Active')})
    elif type(item) is audit:
        if not inspect(root).persistent:
            _deny()
        _only(item, {'organization_id': state.company, 'user_id': state.actor.id,
                    'method': 'POST', 'endpoint': '/master-data', 'entity_type': 'company',
                    'entity_id': root.id, 'action': 'COMPANY_MASTER_SAVED', 'status_code': 200},
              optional={'new_values': (json.dumps({'roles': ['Customer'], 'sharedReason': None}),),
                        'actor_authenticated': (None, False)})
    state.objects[type(item)] = item
    return True


def assert_born_account(db, actor, root):
    state = _current(db)
    if (state is None or state.actor is not actor or state.root is not root
            or not inspect(root).persistent or inspect(root).session is not db):
        _deny()
    for model in _models()[:3]:
        item = state.objects.get(model)
        if item is None or not inspect(item).persistent or not allow_write(db, item):
            _deny()
    from app.branches.models import BranchOwnership
    from sqlalchemy import select
    owner = BranchOwnership.__table__
    proof = db.connection().execute(select(owner.c.company_id, owner.c.branch_id).where(
        owner.c.resource_table == root.__tablename__, owner.c.resource_key == str(root.id))).first()
    if proof is None or tuple(proof) != (state.company, state.branch):
        _deny()
    return state.scope


def enroll_born_account(db, actor, root):
    """Creation-only enrollment before the typed account's native FK flush."""
    scope = assert_born_account(db, actor, root)
    from app.business_packs.models import PackMasterAvailability
    table = PackMasterAvailability.__table__
    key = str(root.id)
    match = (table.c.company_id == scope.company_id, table.c.branch_id == scope.branch_id,
             table.c.context_id == scope.context_id, table.c.resource_table == root.__tablename__,
             table.c.resource_key == key)
    existing = db.connection().execute(select(table.c.id, table.c.active).where(*match)).first()
    if existing:
        if not existing.active:
            _deny()
        return
    db.connection().execute(table.insert().values(company_id=scope.company_id,
        branch_id=scope.branch_id, context_id=scope.context_id,
        resource_table=root.__tablename__, resource_key=key, active=True, revision=1))
