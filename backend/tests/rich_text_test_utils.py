"""Minimum tenant bootstrap for workflow tests using the production middleware."""
import pytest
from contextlib import contextmanager
from app.models.company import Company

@contextmanager
def workflow_seed_scope(db, *, bootstrap_company=True):
    if db.info.get("workflow_seed_scope"):
        yield
        return
    db.info["workflow_seed_scope"] = True
    if bootstrap_company and not db.get(Company,1):
        db.add(Company(id=1,name="Workflow test organization",is_active=True))
        db.commit()

    # These modules explicitly opt in to a provisioned workflow. Record only
    # direct fixture seeds; HTTP writes must earn their ownership in production.
    from sqlalchemy import event, inspect, select
    from fastapi import HTTPException
    from app.branches.catalog import SHARED, resource_key, parents, key_expression
    from app.branches.models import BranchOwnership
    from app.branches.boundary import branch_for_row
    from app.core.tenant_boundary import tenant_company_column
    from app.models.company import Branch
    from app.models.user import User
    from app.models.security_boundary import SecurityResourceOwnership
    from app.core.tenant_boundary import legacy_root
    from app.db.base_class import Base
    from test_identity_utils import complete_workflow_company
    pending = set()
    busy = False

    def remember(session, *_):
        if not busy and not session.info.get('workflow_native_ingestion') and session.info.get("branch_context") is None:
            pending.update(session.new)

    def provision(session):
        nonlocal busy
        if busy or session.info.get('workflow_native_ingestion') or session.info.get("branch_context") is not None:
            return
        pending.update(session.new)
        busy = True
        try:
            session.flush()
            ownership = BranchOwnership.__table__
            todo = [row for row in pending if inspect(row).persistent and row not in session.deleted and (row.__table__.name not in SHARED or legacy_root(type(row)))]
            pending.clear()
            while todo:
                deferred = []
                for row in todo:
                    table = row.__table__
                    key = resource_key(table, {c.name:getattr(row,c.name) for c in table.primary_key})
                    if session.connection().execute(select(ownership.c.resource_key).where(ownership.c.resource_table==table.name,ownership.c.resource_key==key)).first():
                        continue
                    company = getattr(row,"organization_id",None)
                    if company is None and tenant_company_column(type(row)):
                        company = getattr(row,"company_id",None)
                    if company is None:
                        from app.common.models import CommonPerson
                        identities = set()
                        for column in table.c:
                            if any(fk.column.table.name == "users" for fk in column.foreign_keys):
                                value = getattr(row, column.name, None)
                                if value is not None:
                                    identity_company = session.connection().execute(select(CommonPerson.organization_id).where(CommonPerson.user_id == value)).scalar()
                                    if identity_company is not None:
                                        identities.add(identity_company)
                        if len(identities) == 1:
                            company = identities.pop()
                    branch_id = getattr(row,"branch_id",None) if "branch_id" in table.c and any(fk.column.table.name=="branches" for fk in table.c.branch_id.foreign_keys) else None
                    if table.name == "branches":
                        company,branch_id = row.company_id,row.id
                    if branch_id is not None:
                        actual = session.connection().execute(select(Branch.company_id).where(Branch.id==branch_id)).scalar()
                        if company is not None and actual != company:
                            continue  # Intentionally invalid fixture links remain inaccessible.
                        company = actual
                    for column,parent,parent_key in parents(table,Base.metadata.tables):
                        value = getattr(row,column.name,None)
                        if value is None:
                            continue
                        if parent.name == "users" and company is None:
                            from app.common.models import CommonPerson
                            company = session.connection().execute(select(CommonPerson.organization_id).where(CommonPerson.user_id == value)).scalar()
                        owned = session.connection().execute(select(ownership.c.company_id,ownership.c.branch_id).select_from(parent.join(ownership,(ownership.c.resource_table==parent.name)&(ownership.c.resource_key==key_expression(parent)))).where(parent_key==value)).first()
                        if owned:
                            company = company or owned.company_id
                            branch_id = branch_id or owned.branch_id
                    if company is None:
                        companies = session.connection().execute(select(Company.id)).scalars().all()
                        company = companies[0] if len(companies)==1 else None
                    if company is None:
                        deferred.append(row); continue
                    if legacy_root(type(row)):
                        security = SecurityResourceOwnership.__table__
                        if not session.connection().execute(select(security.c.resource_id).where(security.c.resource_table==table.name,security.c.resource_id==row.id)).first():
                            session.connection().execute(security.insert().values(resource_table=table.name,resource_id=row.id,company_id=company))
                    if table.name in SHARED:
                        continue
                    if branch_id is None:
                        branch_id = session.connection().execute(select(Branch.id).where(Branch.company_id==company,Branch.is_active.is_(True)).order_by(Branch.id).limit(1)).scalar()
                    if branch_id is None:
                        deferred.append(row); continue
                    if "organization_id" in table.c and getattr(row,"organization_id",None) is None:
                        row.organization_id = company
                    if tenant_company_column(type(row)) and getattr(row,"company_id",None) is None:
                        row.company_id = company
                    if "branch_id" in table.c and any(fk.column.table.name=="branches" for fk in table.c.branch_id.foreign_keys) and getattr(row,"branch_id",None) is None:
                        row.branch_id = branch_id
                    values = {c.name:getattr(row,c.name) for c in table.c}
                    try:
                        evidence = branch_for_row(session.connection(),table,values,company,Base.metadata.tables,branch_id)
                    except HTTPException:
                        deferred.append(row); continue
                    if len(evidence)>1:
                        continue
                    branch_id = next(iter(evidence),branch_id)
                    session.connection().execute(ownership.insert().values(company_id=company,branch_id=branch_id,resource_table=table.name,resource_key=key,source="explicit-workflow-fixture"))
                if len(deferred)==len(todo):
                    pending.update(deferred); break
                todo = deferred
            if session.query(User.id).first():
                for company in session.connection().execute(select(Branch.company_id).where(Branch.is_active.is_(True)).distinct()).scalars():
                    complete_workflow_company(session,company)
            session.flush()
        finally:
            busy = False

    event.listen(db,"before_flush",remember)
    event.listen(db,"before_commit",provision)
    try:
        yield
    finally:
        event.remove(db,"before_flush",remember)
        event.remove(db,"before_commit",provision)
        db.info.pop("workflow_seed_scope",None)


@pytest.fixture(autouse=True)
def organization_context(db, request):
    # Demo integration modules bootstrap their own company through init_db.
    # Creating a placeholder first would silently make that demo a second tenant.
    with workflow_seed_scope(db, bootstrap_company="init_db" not in vars(request.module)):
        yield
