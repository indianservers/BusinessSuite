"""Public intake belongs to the company's default branch until HR assigns it.

Public applicants cannot choose an ownership scope. Existing ownership is never
replaced; authenticated writes continue through the normal branch boundary.
"""
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from app.db.base_class import Base
from app.branches.models import BranchOwnership, BranchLifecycle
from app.models.company import Branch, Company

APPLICATIONS = "intern_hub_applications"
CHILDREN = ("intern_application_events", "intern_application_documents")


def existing_owner(connection, table, ident):
    owner = BranchOwnership.__table__
    return connection.execute(select(owner.c.company_id, owner.c.branch_id).where(
        owner.c.resource_table == table, owner.c.resource_key == str(ident))).first()


def default_branch(connection, company):
    return connection.execute(select(Branch.id).join(Company, Company.id == Branch.company_id).where(
        Branch.company_id == company, Branch.is_active.is_(True), Company.is_active.is_(True),
        ~Branch.id.in_(select(BranchLifecycle.branch_id).where(BranchLifecycle.deleted_at.is_not(None)))
    ).order_by(Branch.id)).scalars().first()


def put_owner(connection, table, ident, company, branch):
    if existing_owner(connection, table, ident):
        return 0
    connection.execute(BranchOwnership.__table__.insert().values(resource_table=table,
        resource_key=str(ident), company_id=company, branch_id=branch, source="public-intake-default"))
    return 1


def application_owner(connection, ident):
    table = Base.metadata.tables[APPLICATIONS]
    application = connection.execute(select(table.c.id, table.c.organization_id,
        table.c.status, table.c.employee_id).where(table.c.id == ident)).first()
    if not application:
        return None
    owner = existing_owner(connection, APPLICATIONS, ident)
    if owner:
        return owner if owner.company_id == application.organization_id else None
    if application.employee_id is not None or application.status not in {"Pending", "Correction Requested"}:
        return None
    branch = default_branch(connection, application.organization_id)
    if branch is None:
        return None
    put_owner(connection, APPLICATIONS, ident, application.organization_id, branch)
    return application.organization_id, branch


def repair_pending(connection, company, *, apply=False):
    """Repair only explicit-company intake roots and their direct attachments/history."""
    table = Base.metadata.tables[APPLICATIONS]
    ids = connection.execute(select(table.c.id).where(table.c.organization_id == company,
        table.c.employee_id.is_(None), table.c.status.in_(["Pending", "Correction Requested"]))).scalars().all()
    branch = default_branch(connection, company)
    result = {"company_id": company, "default_branch_id": branch, "applications": 0, "children": 0}
    if branch is None:
        return result
    for ident in ids:
        owner = existing_owner(connection, APPLICATIONS, ident)
        if owner is not None and owner.company_id != company:
            continue
        if owner is None:
            result["applications"] += 1
            if apply:
                put_owner(connection, APPLICATIONS, ident, company, branch)
        destination = owner.branch_id if owner else branch
        for name in CHILDREN:
            child = Base.metadata.tables.get(name)
            if child is None:
                continue
            for child_id in connection.execute(select(child.c.id).where(child.c.application_id == ident)).scalars():
                if existing_owner(connection, name, child_id) is None:
                    result["children"] += 1
                    if apply:
                        put_owner(connection, name, child_id, company, destination)
    return result


def remember_public_intake(session, *args):
    if session.info.get("branch_context") is not None:
        return
    from app.core.audit_context import context
    if not context.get():
        return
    pending = session.info.setdefault("public_intake_ownership", [])
    pending.extend(item for item in session.new | session.dirty
                   if inspect(item).mapper.local_table.name in (APPLICATIONS, *CHILDREN))


def stamp_public_intake(session, *args):
    pending = session.info.pop("public_intake_ownership", [])
    if not pending:
        return
    connection = session.connection()
    if not inspect(connection).has_table(BranchOwnership.__tablename__):
        return
    for item in pending:
        name = inspect(item).mapper.local_table.name
        ident = item.id if name == APPLICATIONS else item.application_id
        if ident is None:
            continue  # Unclaimed uploads are private token-controlled resources.
        owner = application_owner(connection, ident)
        if owner and name != APPLICATIONS:
            put_owner(connection, name, item.id, *owner)


def clear_pending(session, *args):
    session.info.pop("public_intake_ownership", None)


def install():
    for name, callback in (("before_flush", remember_public_intake),
                           ("after_flush_postexec", stamp_public_intake),
                           ("after_soft_rollback", clear_pending)):
        if not event.contains(Session, name, callback):
            event.listen(Session, name, callback)
