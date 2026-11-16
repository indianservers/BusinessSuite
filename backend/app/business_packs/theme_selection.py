"""One company Business Pack choice, using existing activations and terminology."""
import hashlib
import json

from fastapi import HTTPException

from app.shared.models import ServicePolicy
from app.shared.business_profile import resolve
from .models import PackActivation
from . import service

KIND = 'business_pack_theme'


def _policy(db, company, *, lock=False):
    query = db.query(ServicePolicy).filter_by(
        organization_id=company, kind=KIND, scope_key=f'business-pack-theme:company:{company}')
    return (query.with_for_update().populate_existing() if lock else query).first()


def _rows(db, company, *, lock=False):
    query = db.query(PackActivation).filter_by(company_id=company).order_by(PackActivation.id)
    return (query.with_for_update().populate_existing() if lock else query).all()


def _state(company, rows, policy):
    active = [row for row in rows if row.state == 'active']
    key = active[0].pack_key if len(active) == 1 else None if active else 'general'
    facts = [(row.id, row.pack_key, row.pack_version, row.state, row.revision) for row in rows]
    revision = hashlib.sha256(json.dumps(
        [company, facts, policy.version if policy else 0,
         policy.values_json if policy else None], sort_keys=True).encode()).hexdigest()
    return {'company_id': company, 'active_key': key, 'selection_revision': revision,
            'multiple_active': len(active) > 1,
            'terminology': resolve([{'business_type': key or 'general'}])}


def configuration(db, actor):
    company = service.company_control(db, actor)
    service._require_schema(db)
    return _state(company, _rows(db, company), _policy(db, company))


def remember(db, actor, company, key):
    """Called under the existing company writer lock; never grants staff access."""
    row = _policy(db, company, lock=True)
    if row is None:
        row = ServicePolicy(organization_id=company, kind=KIND,
            scope_key=f'business-pack-theme:company:{company}', module_key='*',
            values_json={'pack_key': key}, version=1, updated_by=actor.id)
        db.add(row)
    else:
        row.values_json = {'pack_key': key}
        row.version += 1
        row.updated_by = actor.id


def select_only(db, actor, company, chosen):
    """Suspend other company activations; retain contexts, grants and all records."""
    previous = []
    for row in _rows(db, company, lock=True):
        if row.state == 'active' and row is not chosen:
            previous.append(service._output(row))
            row.state = 'suspended'
    remember(db, actor, company, chosen.pack_key if chosen is not None else 'general')
    return previous


def activate(db, actor, data, request=None):
    company = service.company_control(db, actor)
    service._require_schema(db)
    service._lock_company(db, company)
    if service.company_control(db, actor) != company:
        raise HTTPException(403, 'Company authority changed')
    rows, policy = _rows(db, company, lock=True), _policy(db, company, lock=True)
    before = _state(company, rows, policy)
    if before['selection_revision'] != data.expected_selection:
        raise HTTPException(409, 'Business Pack selection changed. Reload before activating.')
    chosen = None
    if data.pack_key != 'general':
        manifest = service._manifest(data.pack_key)
        ready = service.readiness(db, actor, manifest.key)
        if not ready['ready']:
            raise HTTPException(409, {'message': 'Business Pack activation is blocked', 'readiness': ready})
        chosen = next((row for row in rows if
            (row.pack_key, row.pack_version) == (manifest.key, manifest.version)), None)
        if chosen is not None and chosen.state == 'retired':
            raise HTTPException(409, 'A retired Business Pack cannot be activated')
        if chosen is None:
            chosen = PackActivation(company_id=company, pack_key=manifest.key,
                pack_version=manifest.version, state='draft')
            db.add(chosen)
            service._flush(db)
    previous = select_only(db, actor, company, chosen)
    if chosen is not None:
        chosen.state = 'active'
    service._flush(db)
    after = _state(company, _rows(db, company), _policy(db, company))
    service._audit(db, actor, company, 'theme.activated', data.reason,
        {**before, 'previous_activations': previous}, after, request)
    service._commit(db)
    return {**after, 'activation_id': chosen.id if chosen is not None else None}


def selected_profile(db, company):
    """An explicit pack choice supersedes old manually customized profile layers."""
    if _policy(db, company) is None:
        return None
    state = _state(company, _rows(db, company), _policy(db, company))
    if state['multiple_active']:
        return None
    return {**state['terminology'], 'versions': {
        f'business-pack-theme:company:{company}': _policy(db, company).version}}
