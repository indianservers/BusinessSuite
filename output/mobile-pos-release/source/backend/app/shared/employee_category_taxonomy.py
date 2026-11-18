"""Company-owned HRMS work-category hierarchy in existing versioned settings storage."""
from typing import Annotated
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import or_, select
from app.models.company import Branch, Company
from app.models.employee import Employee
from app.shared.models import ServicePolicy
from app.apps.srm.services.commercial import tenant

KIND = 'employee_categories'

def key(company):
    return f'employee-categories:company:{company}'

class Node(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,64}$')
    name: str = Field(min_length=1, max_length=80)
    active: bool = True

    @field_validator('name')
    @classmethod
    def clean_name(cls, value):
        value = ' '.join(value.split())
        if not value or '>' in value:
            raise ValueError('Use a category name without >')
        return value

class Category(Node):
    children: list[Node] = Field(default_factory=list, max_length=100)

class TaxonomyInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Annotated[int, Field(ge=0, strict=True)]
    categories: list[Category] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def unique_nodes(self):
        ids, names = set(), set()
        total = 0
        for category in self.categories:
            if category.id in ids or category.name.casefold() in names:
                raise ValueError('Category ids and names must be unique')
            ids.add(category.id); names.add(category.name.casefold())
            child_names = set()
            for child in category.children:
                total += 1
                if child.id in ids or child.name.casefold() in child_names:
                    raise ValueError('Subcategory ids and names must be unique under their parent')
                if len(category.name + ' > ' + child.name) > 80:
                    raise ValueError('Category and subcategory combined must fit 80 characters')
                ids.add(child.id); child_names.add(child.name.casefold())
        if total > 500:
            raise ValueError('Use at most 500 subcategories')
        return self

def _row(db, company, lock=False):
    query = db.query(ServicePolicy).filter_by(organization_id=company, kind=KIND, scope_key=key(company))
    return (query.with_for_update().populate_existing() if lock else query).first()

def _employee_names(db, company):
    branches = select(Branch.id).where(Branch.company_id == company)
    rows = db.query(Employee.work_categories).filter(Employee.deleted_at.is_(None),
        Employee.status.in_(['Active', 'Probation', 'On Leave']),
        or_(Employee.branch_id.in_(branches), Employee.branch_id.is_(None) & (company == 1))).all()
    return sorted({name for (values,) in rows for name in values or []}, key=str.casefold)

def options(db, actor, legacy_names=None):
    company = tenant(actor)
    row = _row(db, company)
    categories = (row.values_json or {}).get('categories', []) if row else []
    # Preserve existing HRMS category names; hierarchy is explicit, never inferred from co-occurrence.
    legacy = _employee_names(db, company) if legacy_names is None else legacy_names
    known = {node['name'].casefold() for node in categories}
    child_values = {(node['name']+' > '+child['name']).casefold() for node in categories for child in node.get('children', [])}
    import hashlib
    for name in legacy:
        if name.casefold() not in known and name.casefold() not in child_values:
            categories = [*categories, {'id':'legacy-'+hashlib.sha256(name.encode()).hexdigest()[:24], 'name':name, 'active':True, 'children':[], 'legacy':True}]
            known.add(name.casefold())
    items = []
    tree = []
    for node in categories:
        children = [{**child, 'value':node['name']+' > '+child['name'], 'parent_value':node['name']} for child in node.get('children', [])]
        tree.append({**node, 'value':node['name'], 'children':children})
        if node.get('active', True):
            items.append(node['name'])
            items.extend(child['value'] for child in children if child.get('active', True))
    from app.access.catalog import permission_names
    # GET admin inspection is a request mode, not a denial of the actor's real write authority.
    can_manage = bool(actor.is_superuser)
    if not can_manage and not getattr(actor, '_suite_admin_read', False):
        can_manage = 'employee_update' in permission_names(actor)
    elif not can_manage and legacy_names is None:
        from app.access import service
        policy = service.policy_for(db, actor, company)
        actual = service.effective_objects(db, service.resolved_grants(db, policy), 'hrms') if policy and policy.status == 'active' else (actor.role.permissions if not policy and actor.role else [])
        can_manage = any(permission.name == 'employee_update' for permission in actual)
    return {'version':row.version if row else 0, 'categories':tree, 'items':sorted(set(items), key=str.casefold), 'can_manage':can_manage}

def save(db, actor, data, request=None):
    if getattr(actor, '_suite_admin_read', False):
        raise HTTPException(403, 'Read-only access cannot manage HRMS categories')
    from app.apps.srm.services.commercial import require
    require(actor, 'employee_update')
    company = tenant(actor)
    db.query(Company).filter(Company.id == company).with_for_update().one()
    row = _row(db, company, lock=True)
    if (row.version if row else 0) != data.version:
        raise HTTPException(409, 'HRMS categories changed. Reload before saving.')
    previous = (row.values_json or {}).get('categories', []) if row else []
    after = [category.model_dump() for category in data.categories]
    # Keep stable names: renaming would silently change existing employee/service matching.
    incoming = {node['id']:(category['name'] if node is category else category['name']+' > '+node['name']) for category in after for node in [category, *category['children']]}
    for category in previous:
        for node in [category, *category.get('children', [])]:
            if node['id'] not in incoming or incoming[node['id']] != (category['name'] if node is category else category['name']+' > '+node['name']):
                raise HTTPException(422, 'Keep existing category names; archive them and add a new name instead.')
    if row is None:
        row = ServicePolicy(organization_id=company, module_key='hrms', kind=KIND,
            scope_key=key(company), updated_by=actor.id, version=0)
        db.add(row)
    row.values_json = {'categories':after}; row.version += 1; row.updated_by = actor.id
    from app.access.service import audit
    audit(db, actor, company, 'hrms.employee_categories.updated', 'Manage HRMS category hierarchy',
        before={'categories':previous}, after={'categories':after}, request=request)
    db.commit()
    return options(db, actor)
