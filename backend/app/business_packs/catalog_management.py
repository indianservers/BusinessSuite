"""Fixed selected-context catalogue commands; no generic master write bypass.

Canonical detail rows are read/written only through their validated native
parent. They are not private pack copies or globally exempt ORM tables.
"""
import json
import math
import re
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import String, and_, case, cast, exists, func, literal, or_, select

from app.apps.srm.models import SRMProduct
from app.shared.catalog_models import CatalogDetails


def fail(message, status=403):
    raise HTTPException(status, message)


def authority(db, actor, source, kind, action='view', *, read_probe=False):
    from app.shared.catalog import authorize
    from app.access.service import check_background_access
    from app.branches.service import context
    from .access import resolve_context
    from .operations import capabilities
    from .common_core import _native_authority
    scope = db.info.get('business_pack_scope')
    if scope is None:
        fail('A verified selected Business Pack context is required')
    allowed = capabilities(db, actor)
    if ('catalog.manage' if action != 'view' else 'catalog.view') not in allowed:
        fail('Assigned Business Pack role cannot manage this catalog')
    module = 'project_management' if source == 'pms' else source
    if source not in {'srm', 'crm', 'pms'}:
        fail('Unsupported catalog source', 422)
    fingerprint = _native_authority(db, actor, scope.company_id)
    branch = context(db, actor, scope.company_id, str(scope.branch_id))
    if branch != db.info.get('branch_context') or resolve_context(db, actor, branch, scope.context_id) != scope:
        fail('Catalog authorization changed; reload before continuing')
    if action != 'view' and (not scope.writable or scope.branch_id not in branch.writable or db.info.get('security_write_request') is False and not read_probe):
        fail('A writable catalog branch is required')
    if read_probe:
        authorize(actor,source,kind,False,db=db)
        grant=_module_grant(db,actor,scope,module)
        names=set(grant.get('permissions',()))
        required={'srm':{'srm_manage','srm_admin'},'pms':{'pms_admin','pms_manage_projects'},
            'crm':{'crm_manage','crm_admin','crm_products_manage'}}[source]
        if not actor.is_superuser and (not grant.get('enabled') or action not in grant.get('actions',()) or not names.intersection(required)):
            fail('Native catalog management permission is required')
        from app.enterprise.controls import governance_module_check
        governance_module_check(db,actor,scope.company_id,module,action)
    else:
        authorize(actor, source, kind, action != 'view', db=db)
        check_background_access(db, actor, module, action)
    return scope, fingerprint


def _query(db, actor, source, scope, kind=None, *, exclude_workspace=False):
    from app.shared.catalog_branches import availability_clause
    from app.shared.catalog import catalog_resource
    query = db.query(SRMProduct).filter(SRMProduct.organization_id == scope.company_id, SRMProduct.deleted_at.is_(None),
        availability_clause(SRMProduct, scope.branch_id))
    if kind:
        query = query.filter(SRMProduct.product_type == 'service' if kind == 'service' else or_(SRMProduct.product_type.is_(None), SRMProduct.product_type != 'service'))
    if source == 'crm':
        from app.apps.crm.api.router import _apply_record_visibility
        query = _apply_record_visibility(query, catalog_resource(), actor, db)
    if exclude_workspace:
        # Fixed canonical-parent projection, not a globally shared metadata
        # model. Unreviewed private workspace offerings never enter counts,
        # sorting, facets or pages; direct detail reads still explain safely.
        from .catalog_predicate import _workspace_predicate
        private = _workspace_predicate(db,scope)
        query = query.filter(~private)
    return query


def _detail(db, product, kind, *, lock=False):
    """Only exact canonical parent, kind and company; reject malformed aliases."""
    table = CatalogDetails.__table__
    query = select(table).where(or_(table.c.product_id == product.id, table.c.service_id == product.id))
    if lock:
        query = query.with_for_update()
    rows = db.connection().execute(query).mappings().all()
    if len(rows) > 1:
        fail('Catalog metadata identity requires reconciliation', 503)
    if not rows:
        return None
    row = dict(rows[0])
    if (row['organization_id'] != product.organization_id or row[kind + '_id'] != product.id
            or row[('service' if kind == 'product' else 'product') + '_id'] is not None):
        fail('Catalog metadata parent is inconsistent', 503)
    if row['workspace_id'] is not None:
        fail('Workspace catalog management is not integrated for this context', 503)
    return row


def _parent(db, actor, source, scope, kind, ident, *, lock=False):
    from app.apps.srm.service_checkout import _source_scope
    query = _query(db, actor, source, scope, kind).filter(SRMProduct.id == ident)
    if lock:
        query = query.populate_existing().with_for_update()
    product = query.first()
    if product is None:
        fail('Catalog item not found', 404)
    _source_scope(db, scope, scope.company_id, scope.branch_id, SRMProduct, product.id, master=True)
    return product


def _output(product, kind, detail, scope=None, *, db=None, actor=None):
    from app.shared.catalog import output
    result=output(product, kind, SimpleNamespace(**detail) if detail else None)
    if scope is not None and scope.pack_key=='pharma' and kind=='product':
        result['pharma_lot_tracking']=bool(product.batch_tracking and product.expiry_tracking)
        result['pharma_warehouse_id']=product.default_warehouse_id
    if scope is not None and scope.pack_key=='restaurant' and kind=='product':
        from .restaurant.modifiers import catalog, menu_groups
        from pydantic import ValidationError
        try:
            definition = catalog(product)
        except ValidationError:
            fail('Modifier definition requires correction',409)
        if definition.groups:
            if db is None or actor is None:
                fail('Modifier definition requires its native source context',503)
            menu_groups(db, actor, scope, product, (product.metadata_json or {}).get('currency','INR'))
        result['restaurant_modifiers']=definition.model_dump(mode='json')
    return result


def _module_grant(db,actor,scope,module):
    """Fresh facts, independent of foreground filtering/inspection overlays."""
    from app.access.models import AccessPolicy
    from app.access.service import ACTIONS,resolved_grants
    from app.access.entitlements import apply
    from app.access.catalog import permission_module
    from app.models.user import Permission,role_permissions
    from app.branches.models import BranchGrant
    from app.branches.roles import effective_grants
    connection=db.connection()
    policy=connection.execute(select(AccessPolicy.status,AccessPolicy.grants,AccessPolicy.version).where(
        AccessPolicy.company_id==scope.company_id,AccessPolicy.user_id==actor.id)).mappings().first()
    if policy and not actor.is_superuser:
        if policy['status']!='active':fail('Native module policy is inactive')
        base=resolved_grants(db,SimpleNamespace(company_id=scope.company_id,grants=policy['grants']))
    else:
        facts=connection.execute(select(Permission.name,Permission.module).join(role_permissions,
            role_permissions.c.permission_id==Permission.id).where(role_permissions.c.role_id==actor.role_id)).mappings()
        names={row['name'] for row in facts if permission_module(SimpleNamespace(**dict(row)))==module}
        base=apply(db,scope.company_id,{module:{'enabled':bool(names or actor.is_superuser),'permissions':sorted(names),
            'actions':ACTIONS if actor.is_superuser or any('manage' in name or 'admin' in name for name in names) else ['view'],
            'scope':'organization' if actor.is_superuser else 'own'}})
    grants=effective_grants(db,actor,scope.company_id,scope.branch_id,base,administrative_read=False,stamp=False)
    grant=dict((grants or {}).get(module,{}))
    branch=connection.execute(select(BranchGrant.module_grants).where(BranchGrant.company_id==scope.company_id,
        BranchGrant.branch_id==scope.branch_id,BranchGrant.user_id==actor.id)).first()
    grant['_native_scoped']=bool(policy or branch and branch[0] is not None)
    return grant


def _item_editable(db,actor,scope,source,product,can_manage,grant=None):
    if not can_manage:return False
    grant=grant if grant is not None else _module_grant(db,actor,scope,'project_management' if source=='pms' else source)
    if actor.is_superuser:return True
    if 'edit' not in grant.get('actions',()):return False
    if not grant.get('_native_scoped'):
        if source=='crm':
            from app.apps.crm.api.router import _crm_role_key
            return _crm_role_key(actor) in {'admin','viewer','super_admin'} or product.created_by==actor.id
        return True
    native_scope=grant.get('scope','own')
    if native_scope=='organization':return True
    if native_scope=='assigned':return False  # This master has no assignment column.
    if native_scope=='own':return product.created_by==actor.id
    from app.models.employee import Employee
    from app.models.company import Branch
    table=Employee.__table__
    employee=db.connection().execute(select(table.c.id,table.c.branch_id,table.c.department_id).join(
        Branch.__table__,Branch.id==table.c.branch_id).where(table.c.user_id==actor.id,Branch.company_id==scope.company_id)).first()
    if not employee:return False
    where={'team':table.c.reporting_manager_id==employee.id,'branch':table.c.branch_id==employee.branch_id,
        'department':table.c.department_id==employee.department_id if employee.department_id else False}.get(native_scope,False)
    own=product.created_by==actor.id and native_scope=='team'
    return own or bool(db.connection().execute(select(table.c.id).join(Branch.__table__,Branch.id==table.c.branch_id).where(
        Branch.company_id==scope.company_id,table.c.user_id==product.created_by,where)).first())


def features(db, actor, scope):
    """Advisory native facts; never a mutation or an operational grant."""
    result=dict(selected_context=True,workspaces=False,follow_ups=False,image_upload=False,
        imports=False,exports=False,branch_reuse=False,archive=False,duplicate=False,scheduling_configure=False)
    result['pharma_lot_tracking']=scope.pack_key=='pharma'
    try:
        from app.access.entitlements import enforce
        from app.enterprise.controls import governance_module_check
        from app.branches.service import context
        from app.apps.srm.service_checkout import _authority
        from .common_core import _native_authority
        _native_authority(db,actor,scope.company_id)
        grant=_module_grant(db,actor,scope,'srm')
        branch=context(db,actor,scope.company_id,str(scope.branch_id))
        if scope.branch_id not in branch.writable:return result
        if not actor.is_superuser and (not grant.get('enabled') or 'create' not in grant.get('actions',[]) or
                not {'srm_manage','srm_admin'}.intersection(grant.get('permissions',[]))):return result
        enforce(db,scope.company_id,'srm')
        governance_module_check(db,actor,scope.company_id,'srm','create')
        company,selected,verified=_authority(db,actor,configuration=True,write=False,order=False,pure_probe=True)
        result['scheduling_configure']=(company,selected,verified)==(scope.company_id,scope.branch_id,scope)
    except HTTPException as error:
        if error.status_code not in {403,404,409,503}:raise
    return result


def get_item(db, actor, source, kind, ident):
    scope, _ = authority(db, actor, source, kind)
    product = _parent(db, actor, source, scope, kind, ident)
    try:
        authority(db,actor,source,kind,'edit',read_probe=True)
        editable=_item_editable(db,actor,scope,source,product,True)
    except HTTPException as error:
        if error.status_code!=403:raise
        editable=False
    return {**_output(product, kind, _detail(db, product, kind),scope,db=db,actor=actor),'features':features(db,actor,scope),'can_edit':editable}


def list_items(db, actor, source, *, kind=None, search='', category='', status='Active', workspace_id=None,
        sort='name', direction='asc', page=1, per_page=24, tag='', item_keys=None, key_order=False,
        include_facets=False, price_book_id=None):
    if workspace_id is not None or price_book_id is not None:
        fail('Workspace and price-list catalog projections are not integrated for this context', 503)
    keys = None
    if item_keys is not None:
        keys = list(dict.fromkeys(item_keys.split(',') if item_keys else []))
        if len(keys) > 500 or any(not re.fullmatch(r'(product|service):[1-9][0-9]{0,15}', value) for value in keys):
            fail('Choose up to 500 valid catalog records', 422)
    permissions = {}
    scope = None
    for selected in ([kind] if kind else ['product', 'service']):
        try:
            current, _ = authority(db, actor, source, selected)
        except HTTPException as error:
            if kind or error.status_code != 403:
                raise
            continue
        scope = current
        try:
            authority(db, actor, source, selected, 'edit',read_probe=True)
            permissions[selected] = True
        except HTTPException as error:
            if error.status_code != 403:
                raise
            try:
                authority(db, actor, source, selected, 'create',read_probe=True)
                permissions[selected] = True
            except HTTPException as create_error:
                if create_error.status_code != 403:
                    raise
                permissions[selected] = False
    if not permissions:
        fail('Catalog access is required')
    from .catalog_predicate import _projection
    with _projection(db,actor,scope,source,tuple(permissions)):
        return _list_page(db,actor,source,scope,permissions,kind=kind,search=search,category=category,status=status,
            sort=sort,direction=direction,page=page,per_page=per_page,tag=tag,keys=keys,key_order=key_order,include_facets=include_facets)


def _list_page(db,actor,source,scope,permissions,*,kind,search,category,status,sort,direction,page,per_page,tag,keys,key_order,include_facets):
    query = _query(db, actor, source, scope, kind, exclude_workspace=True)
    item_kind = case((SRMProduct.product_type == 'service', literal('service')), else_=literal('product'))
    query = query.filter(item_kind.in_(list(permissions)))
    if status != 'all':
        query = query.filter(SRMProduct.active == (status == 'Active'))
    if category:
        query = query.filter(or_(SRMProduct.category_name == category,
            cast(SRMProduct.metadata_json['catalog_categories'], String).contains(json.dumps(category,ensure_ascii=False),autoescape=True)))
    if search:
        query = query.filter(or_(SRMProduct.item_name.icontains(search, autoescape=True),
            SRMProduct.sku.icontains(search, autoescape=True), SRMProduct.description.icontains(search, autoescape=True)))
    if keys is not None:
        query = query.filter(or_(*( (item_kind == value.split(':')[0]) & (SRMProduct.id == int(value.split(':')[1])) for value in keys))) if keys else query.filter(False)
    facets = None
    if include_facets:
        # Scalar mapped-column ORM projections keep native and PackScope criteria
        # active; never compile an unguarded query.statement for Core execution.
        categories = query.with_entities(SRMProduct.category_name).distinct().order_by(SRMProduct.category_name).limit(1001).all()
        tag_value = SRMProduct.metadata_json['catalog_tags']
        if db.get_bind().dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSONB
            tag_value = cast(tag_value, JSONB)
        arrays = query.with_entities(tag_value).distinct().order_by(tag_value).limit(1001).all()
        tags = {value for (values,) in arrays[:1000] if isinstance(values,list) for value in values if isinstance(value,str)}
        category_labels = query.with_entities(SRMProduct.metadata_json['catalog_categories']).limit(1000).all()
        all_categories = {value for (value,) in categories[:1000] if value}
        all_categories.update(label for (values,) in category_labels if isinstance(values,list) for label in values)
        facets = {'categories': sorted(all_categories), 'tags': sorted(tags),
            'has_more': len(categories)>1000 or len(arrays)>1000}
    if tag:
        normalized = tag.strip().lower()
        if db.get_bind().dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import JSONB
            query = query.filter(cast(SRMProduct.metadata_json, JSONB).contains({'catalog_tags':[normalized]}))
        else:
            # The native ItemInput contract limits tags to twenty strings. Use
            # mapped JSON columns only: raw json_each aliases are deliberately
            # not trusted by the pack ORM guard. Invalid historic arrays fail
            # explicitly rather than silently truncating their matches.
            tag_type = func.json_type(SRMProduct.metadata_json,'$.catalog_tags')
            malformed = query.filter(or_(tag_type.notin_(['array','null']),
                func.json_array_length(SRMProduct.metadata_json,'$.catalog_tags')>20)).with_entities(SRMProduct.id).first()
            if malformed:
                fail('Catalog tags require native metadata reconciliation',503)
            query = query.filter(or_(*(SRMProduct.metadata_json['catalog_tags'][index].as_string()==normalized for index in range(20))))
    total = query.with_entities(func.count(SRMProduct.id)).scalar()
    sort_column = {'name':SRMProduct.item_name,'price':func.coalesce(SRMProduct.sales_rate,0),
        'category':func.coalesce(SRMProduct.category_name,''),'code':SRMProduct.sku}[sort]
    ordering = sort_column.asc() if direction=='asc' else sort_column.desc()
    if key_order and keys:
        ordering = case({key:position for position,key in enumerate(keys)},
            value=item_kind+literal(':')+cast(SRMProduct.id,String),else_=len(keys)).asc()
    products = query.order_by(ordering,item_kind.asc(),SRMProduct.id.asc()).offset((page-1)*per_page).limit(per_page).all()
    items = []
    write_grant=_module_grant(db,actor,scope,'project_management' if source=='pms' else source)
    for product in products:
        selected = 'service' if product.product_type=='service' else 'product'
        from app.apps.srm.service_checkout import _source_scope
        _source_scope(db,scope,scope.company_id,scope.branch_id,SRMProduct,product.id,master=True)
        items.append({**_output(product,selected,_detail(db,product,selected),scope,db=db,actor=actor),'can_edit':_item_editable(db,actor,scope,source,product,permissions[selected],grant=write_grant)})
    flags=features(db,actor,scope)
    return {'items':[{**item,'features':flags} for item in items],'total':total,'pages':math.ceil(total/per_page),'permissions':permissions,'features':flags,
        **({'facets':facets} if facets is not None else {})}



def save_item(db, actor, source, data, ident=None):
    from app.apps.srm.services.commercial import lock_tenant
    from app.branches.models import BranchOwnership
    from app.models.audit import AuditLog
    scope, fingerprint = authority(db, actor, source, data.kind, 'edit' if ident else 'create')
    if (data.pharma_lot_tracking is not None or data.pharma_warehouse_id is not None) and (scope.pack_key!='pharma' or source!='srm' or data.kind!='product'):
        fail('Lot configuration requires a Pharma Sales product',422)
    modifier_supplied = 'restaurant_modifiers' in data.model_fields_set
    if modifier_supplied and (scope.pack_key!='restaurant' or source!='srm' or data.kind!='product' or data.restaurant_modifiers is None):
        fail('Modifier configuration requires a Restaurant Sales product and explicit definition',422)
    # Never discard unsupported submitted values or stored metadata.
    if data.workspace_id is not None or data.follow_up is not None:
        fail('Workspace and follow-up editing are not integrated for this context', 503)
    if not ident and data.branch_availability is not None and not (data.branch_availability.scope == 'current' or
            data.branch_availability.scope == 'selected' and data.branch_availability.branch_ids == [scope.branch_id]):
        fail('Use native administrator enrollment to share catalog availability', 503)
    if ident and data.version is None:
        fail('The current catalog version is required', 422)
    with db.begin_nested():
        lock_tenant(db, actor)
        fresh, current = authority(db, actor, source, data.kind, 'edit' if ident else 'create')
        if fresh != scope or current != fingerprint:
            fail('Native catalog authority changed while waiting for the writer lock')
        product = _parent(db, actor, source, scope, data.kind, ident, lock=True) if ident else None
        detail = _detail(db, product, data.kind, lock=True) if product else None
        if product and data.branch_availability is not None:
            supplied = data.branch_availability.model_dump()
            if supplied['scope'] == 'current':
                supplied = {'scope':'selected','branch_ids':[scope.branch_id]}
            from app.shared.catalog import output as native_catalog_output
            if supplied != native_catalog_output(product,data.kind,SimpleNamespace(**detail) if detail else None)['branch_availability']:
                fail('Catalog branch availability cannot change through this command',503)
            # Retain the native ceiling even when the editor echoes unchanged
            # availability: every previously shared branch must be writable.
            from app.shared.branch_availability import active_branches,check_destinations
            from app.shared.catalog_branches import is_available
            from app.branches.service import access
            from app.shared.catalog import authorize
            existing = {branch for branch in active_branches(db,scope.company_id) if is_available(product,branch)}
            if not existing <= access(db,actor,scope.company_id)[1]:
                fail('Write access is required for existing shared branches')
            check_destinations(db,actor,existing,'project_management' if source=='pms' else source,'edit',
                lambda:authorize(actor,source,data.kind,True,db=db))
        if ident and data.version != (detail['version'] if detail else 0):
            fail('This item changed. Reload it before saving.', 409)
        # Lock/recheck enrolled availability, including revocation after a wait.
        from .models import PackMasterAvailability
        if product:
            available = PackMasterAvailability.__table__
            enrolled = db.connection().execute(select(available.c.id).where(available.c.company_id == scope.company_id,
                available.c.branch_id == scope.branch_id, available.c.context_id == scope.context_id,
                available.c.resource_table == 'srm_products', available.c.resource_key == str(product.id), available.c.active.is_(True)).with_for_update()).first()
            if not enrolled:
                fail('Catalog source is no longer available in this context')
        if authority(db, actor, source, data.kind, 'edit' if ident else 'create') != (scope, fingerprint):
            fail('Catalog authority changed before save')
        if product is None:
            product = SRMProduct(organization_id=scope.company_id, created_by=actor.id,
                product_type='service' if data.kind == 'service' else 'stock', track_inventory=data.kind != 'service',
                sku=data.code, item_name=data.name, metadata_json={'catalog_branches': {'default': False, 'overrides': {str(scope.branch_id): True}}})
            db.add(product)
            db.flush()  # Existing native boundary stamps only this newly born master.
            from app.apps.srm.service_checkout import _source_scope
            _source_scope(db,scope,scope.company_id,scope.branch_id,SRMProduct,product.id,master=True)
        before = {column.name: getattr(product, column.name) for column in product.__table__.c}
        metadata = dict(product.metadata_json or {})
        metadata.update(currency=data.currency, images=data.images)
        if data.category_ids is not None:
            from app.shared.catalog_categories import selection
            ids, labels = selection(db, actor, data.category_ids)
            metadata.update(catalog_category_ids=ids, catalog_categories=labels)
            data.category = labels[0].split(' > ')[0] if labels else ''
        if modifier_supplied:
            from .restaurant.modifiers import validate_catalog
            metadata['restaurant_modifiers'] = validate_catalog(db, actor, scope, product.id, data.currency, data.restaurant_modifiers)
        if data.tags is not None:
            metadata['catalog_tags'] = data.tags
        values = dict(item_name=data.name, sku=data.code, description=data.description, category_name=data.category,
            sales_rate=data.price, gst_rate=data.tax, unit_code=data.unit, active=data.status == 'Active', metadata_json=metadata)
        for field, column in [('barcode','barcode'),('hsn_code','hsn_code'),('cost','purchase_rate'),('mrp','mrp'),('reorder_level','reorder_level'),('track_inventory','track_inventory')]:
            value = getattr(data, field)
            if value is not None:
                values[column] = (value or None) if field in {'barcode','hsn_code'} else value
        if data.kind == 'service':
            values['track_inventory'] = False
        if data.pharma_lot_tracking is not None:
            if data.pharma_lot_tracking and (data.track_inventory is False or before['serial_tracking']):
                fail('Batch and expiry tracking requires physical stock without serial tracking',422)
            values.update(batch_tracking=data.pharma_lot_tracking,expiry_tracking=data.pharma_lot_tracking)
            if data.pharma_lot_tracking:values['track_inventory']=True
        if scope.pack_key=='pharma' and source=='srm' and data.kind=='product' and (data.pharma_lot_tracking or data.pharma_warehouse_id is not None):
            from app.apps.srm.models import SRMWarehouse
            from app.apps.srm.stock_resource import _native_branch
            from app.apps.srm.service_checkout import _source_scope
            warehouse_id=data.pharma_warehouse_id or before['default_warehouse_id']
            if not warehouse_id:fail('Choose an available default warehouse for medicine lots',422)
            w=SRMWarehouse.__table__
            if not db.connection().scalar(select(w.c.id).where(w.c.id==warehouse_id,w.c.organization_id==scope.company_id,w.c.active.is_(True)).with_for_update()):
                fail('Eligible medicine warehouse is unavailable',404)
            _source_scope(db,scope,scope.company_id,scope.branch_id,SRMWarehouse,warehouse_id,master=True)
            _native_branch(db,w.name,warehouse_id,scope.company_id,scope.branch_id)
            values['default_warehouse_id']=warehouse_id
        from .pharma.eligibility import managed_product
        if managed_product(db,scope.company_id,product.id) and (values.get('track_inventory',before['track_inventory']) is not True
                or values.get('batch_tracking',before['batch_tracking']) is not True or values.get('expiry_tracking',before['expiry_tracking']) is not True
                or before['serial_tracking'] or data.kind!='product'):
            fail('Managed batch stock cannot change its stock classification or disable lot tracking',409)
        connection = db.connection()
        changed_product = connection.execute(SRMProduct.__table__.update().where(SRMProduct.id == product.id,
            SRMProduct.organization_id == scope.company_id, SRMProduct.created_by == before['created_by'] if before['created_by'] is not None else SRMProduct.created_by.is_(None)).values(**values))
        if changed_product.rowcount != 1:
            fail('Catalog source changed during save', 409)
        table = CatalogDetails.__table__
        details = dict(unit=data.unit, images=data.images, custom_fields=data.custom_fields,
            pricing_options=[price.model_dump(mode='json') for price in data.pricing_options], version=(detail['version'] if detail else 0)+1)
        if detail:
            changed = connection.execute(table.update().where(table.c.id == detail['id'], table.c.organization_id == scope.company_id,
                table.c[data.kind+'_id'] == product.id, table.c.version == detail['version']).values(**details))
            if changed.rowcount != 1:
                fail('Catalog version changed during save', 409)
            details = {**detail, **details}
        else:
            details.update(organization_id=scope.company_id, product_id=product.id if data.kind == 'product' else None,
                service_id=product.id if data.kind == 'service' else None, workspace_id=None)
            connection.execute(table.insert().values(**details))
        audit = AuditLog.__table__
        audit_id = connection.execute(audit.insert().values(organization_id=scope.company_id,user_id=actor.id,method='CATALOG',
            endpoint=f'/catalog/items/{data.kind}/{product.id}',entity_type='crm_catalog',entity_id=product.id,
            action='UPDATE' if ident else 'CREATE',new_values=json.dumps({'context_id':scope.context_id,'version':details['version']}),
            description='Selected native catalog command').returning(audit.c.id)).scalar_one()
        connection.execute(BranchOwnership.__table__.insert().values(company_id=scope.company_id,branch_id=scope.branch_id,
            resource_table='audit_logs',resource_key=str(audit_id),source='typed-catalog-command'))
        result = {**_output(SimpleNamespace(**{**before, **values}), data.kind, details,scope,db=db,actor=actor),'features':features(db,actor,scope)}
        db.expire(product)
    return result
