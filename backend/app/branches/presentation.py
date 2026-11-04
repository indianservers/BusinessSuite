from sqlalchemy import inspect, select, tuple_
from app.branches.models import BranchOwnership
from app.branches.catalog import resource_key
from app.models.company import Branch


def prefetch_branch_names(db, records):
    """Batch display metadata for already-authorized read rows, never access rules."""
    if db.info.get('security_write_request'):
        return
    owners=db.info.setdefault('branch_display_ownership',{})
    names=db.info.setdefault('branch_display_names',{})
    identities=[]
    for record in records:
        state=inspect(record);table=state.mapper.local_table
        company=getattr(record,'organization_id',None)
        ctx=db.info.get('branch_context')
        if company is None and ctx:company=ctx.company_id
        if company is None:continue
        key=(table.name,company,resource_key(table,{column.name:getattr(record,column.name) for column in table.primary_key}))
        identities.append((key,record))
    missing=[key for key,_ in identities if key not in owners]
    for key in missing:owners[key]=None
    if missing:
        ownership=BranchOwnership.__table__
        for table,company,key,branch in db.connection().execute(select(ownership.c.resource_table,ownership.c.company_id,ownership.c.resource_key,ownership.c.branch_id).where(tuple_(ownership.c.resource_table,ownership.c.company_id,ownership.c.resource_key).in_(missing))):
            owners[table,company,key]=branch
    missing_names={(key[1],owners[key] if owners[key] is not None else getattr(record,'branch_id',None)) for key,record in identities}
    missing_names={key for key in missing_names if key[1] is not None and key not in names}
    for key in missing_names:names[key]=None
    if missing_names:
        for company,branch,name in db.connection().execute(select(Branch.__table__.c.company_id,Branch.__table__.c.id,Branch.__table__.c.name).where(tuple_(Branch.__table__.c.company_id,Branch.__table__.c.id).in_(missing_names))):
            names[company,branch]=name


def record_branch_name(record):
    state = inspect(record)
    db = state.session
    if db is None:
        return None
    table = state.mapper.local_table
    company = getattr(record, "organization_id", None)
    ctx = db.info.get("branch_context")
    if company is None and ctx:
        company = ctx.company_id
    if company is None:
        return None
    key = resource_key(table, {c.name: getattr(record, c.name) for c in table.primary_key})
    identity=(table.name,company,key)
    owners=db.info.get('branch_display_ownership',{})
    branch = owners[identity] if not db.info.get('security_write_request') and identity in owners else db.connection().execute(select(BranchOwnership.branch_id).where(BranchOwnership.resource_table == table.name, BranchOwnership.resource_key == key, BranchOwnership.company_id == company)).scalar()
    if branch is None:
        branch = getattr(record, "branch_id", None)
    if branch is None:
        return None
    cache = db.info.setdefault("branch_display_names", {})
    if (company, branch) not in cache:
        cache[company, branch] = db.connection().execute(select(Branch.name).where(Branch.id == branch, Branch.company_id == company)).scalar()
    return cache[company, branch]
