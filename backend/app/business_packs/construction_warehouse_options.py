"""Closed canonical warehouse name selector; no stock or generic inventory lease."""
from fastapi import HTTPException
from sqlalchemy import exists, select


def options(db, actor, search='', offset=0):
    from app.access.service import check_background_access
    from app.apps.srm.industry_api import context
    from app.apps.srm.services.commercial import require
    from app.apps.srm.service_checkout import _source_scope
    from app.apps.srm.models import SRMWarehouse
    from app.branches.models import BranchOwnership
    from .models import PackMasterAvailability, PackRecordOwnership
    from .operations import require as pack_require
    from .boundary import _current
    from .common_core import _native_authority
    if not isinstance(search, str) or len(search) > 180 or type(offset) is not int or not 0 <= offset <= 100000:
        raise HTTPException(422, 'Invalid warehouse selector search or offset')
    def authority():
        require(actor, 'srm_view', 'srm_manage', 'srm_admin')
        check_background_access(db, actor, 'srm', 'view', stamp=False)
        branch = context(db, actor)
        pack_require(db, actor, 'materials.request')
        scope = db.info.get('business_pack_scope')
        if scope is None or scope.pack_key != 'construction' or scope.branch_id != branch:
            raise HTTPException(403, 'An authorized Construction material context is required')
        _current(scope, db.connection())
        return scope, _native_authority(db, actor, scope.company_id)
    scope, epoch = authority()
    w, b, a, p = (m.__table__ for m in (SRMWarehouse, BranchOwnership, PackMasterAvailability, PackRecordOwnership))
    from sqlalchemy import String, cast
    key = cast(w.c.id, String)
    stmt = select(w.c.id, w.c.warehouse_name).where(
        w.c.organization_id == scope.company_id, w.c.active.is_(True),
        exists(select(b.c.resource_key).where(b.c.resource_table == w.name, b.c.resource_key == key,
            b.c.company_id == scope.company_id, b.c.branch_id == scope.branch_id)),
        exists(select(a.c.id).where(a.c.resource_table == w.name, a.c.resource_key == key,
            a.c.company_id == scope.company_id, a.c.branch_id == scope.branch_id,
            a.c.context_id == scope.context_id, a.c.active.is_(True))),
        ~exists(select(p.c.id).where(p.c.resource_table == w.name, p.c.resource_key == key)))
    if search.strip():
        literal = search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        stmt = stmt.where(w.c.warehouse_name.ilike('%' + literal + '%', escape='\\'))
    stmt = stmt.order_by(w.c.warehouse_name, w.c.id).offset(offset).limit(51)
    rows = db.connection().execute(stmt).all()
    for row in rows[:50]:
        _source_scope(db, scope, scope.company_id, scope.branch_id, SRMWarehouse, row.id, master=True)
    if authority() != (scope, epoch) or db.connection().execute(stmt).all() != rows:
        raise HTTPException(409, 'Warehouse availability changed; reload options')
    return {'items': [{'id': row.id, 'name': row.warehouse_name} for row in rows[:50]], 'has_more': len(rows) > 50}
