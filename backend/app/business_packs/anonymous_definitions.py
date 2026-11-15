"""Closed definition projection for a newly born anonymous counter account.

This is not a customer reader or an operational CRM grant. The canonical
validator keeps enforcing required fields, including hidden required fields.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from copy import deepcopy
from weakref import WeakKeyDictionary

from fastapi import HTTPException
from sqlalchemy import select


@dataclass(frozen=True)
class Definition:
    id: int
    field_key: str
    field_name: str | None
    label: str
    field_type: str
    options_json: object
    is_required: bool
    is_unique: bool
    is_visible: bool


@dataclass(frozen=True)
class _Lease:
    actor: object
    company: int
    branch: int
    scope: object
    payload: object
    snapshot: str


_leases = WeakKeyDictionary()


def _deny():
    raise HTTPException(403, 'Anonymous account definition authority changed')


def _input(payload):
    from app.shared.master_data import CompanyInput
    if type(payload) is not CompanyInput:
        _deny()
    if (payload.customFields or payload.version is not None
            or payload.primaryContactId is not None or payload.newPrimaryContact is not None
            or payload.email or payload.phone or payload.phone_country_code
            or payload.addresses or payload.taxRegistrations or payload.financialData
            or payload.communicationChannels or payload.roles != ['Customer']
            or not payload.country or payload.branch_availability is not None):
        _deny()
    return payload.model_dump_json()


def _authority(db, actor):
    from app.apps.srm.service_checkout import _authority as checkout_authority
    from app.access.settings_hub import context, can_edit_company
    company, branch, scope = checkout_authority(db, actor, configuration=True)
    control = context(db, actor)
    if scope is None or not control['admin'] or not can_edit_company(control):
        _deny()
    if db.info.get('business_pack_scope') != scope:
        _deny()
    return company, branch, scope


@contextmanager
def anonymous_company_birth(db, actor, payload, *, source='srm'):
    """Lease only the exact canonical CREATE input, never an existing account.

    The caller must enclose write_company in this context and retain its native
    create validation. No authority is stored on the request or model itself.
    """
    if source != 'srm' or db in _leases:
        _deny()
    snapshot = _input(payload)
    from app.apps.srm.services.commercial import lock_tenant
    lock_tenant(db, actor)
    company, branch, scope = _authority(db, actor)
    lease = _Lease(actor, company, branch, scope, payload, snapshot)
    _leases[db] = lease
    try:
        yield
    finally:
        if _leases.get(db) is lease:
            del _leases[db]


def assert_company_birth_input(db, actor, source, payload, row):
    """Bind the canonical writer to the exact certified CREATE invocation."""
    lease = _leases.get(db)
    if lease is None:
        return
    if (actor is not lease.actor or source != 'srm' or payload is not lease.payload
            or row is not None or _input(payload) != lease.snapshot):
        _deny()
    company, branch, scope = _authority(db, actor)
    if (company, branch, scope) != (lease.company, lease.branch, lease.scope):
        _deny()


def definitions_for_birth(db, entity, organization_id, *, include_hidden=True):
    """Return None outside the lease so the native reader remains unchanged."""
    lease = _leases.get(db)
    if lease is None:
        return None
    if (entity != 'companies' or type(organization_id) is not int
            or organization_id != lease.company or type(include_hidden) is not bool
            or _input(lease.payload) != lease.snapshot):
        _deny()
    company, branch, scope = _authority(db, lease.actor)
    if (company, branch, scope) != (lease.company, lease.branch, lease.scope):
        _deny()
    # This native catalogue is explicitly company-shared in branches.catalog.
    # Exact-company provenance deliberately has no legacy NULL fallback.
    from app.apps.crm.models import CRMCustomField
    table = CRMCustomField.__table__
    columns = ('id', 'field_key', 'field_name', 'label', 'field_type',
               'options_json', 'is_required', 'is_unique', 'is_visible')
    statement = select(*(table.c[name] for name in columns)).where(
        table.c.organization_id == company, table.c.entity == 'companies',
        table.c.deleted_at.is_(None), table.c.is_active.is_(True))
    if not include_hidden:
        statement = statement.where(table.c.is_visible.is_(True))
    rows = db.connection().execute(statement.order_by(
        table.c.position.asc(), table.c.label.asc())).mappings()
    # Detached scalar snapshots cannot expose lazy relationships or field values.
    return tuple(Definition(**{name: deepcopy(row[name]) for name in columns}) for row in rows)
