"""Bounded read-only authorization inputs, including during native flush hooks."""
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import and_, cast, event, exists, inspect, or_, select, String
from sqlalchemy.orm import Session, with_loader_criteria


class _ReadOnlyAuthority(Session):
    def _deny(self, *args, **kwargs):
        raise HTTPException(403, 'AI authority snapshots are read-only')

    add = add_all = delete = commit = rollback = flush = _deny
    bulk_save_objects = bulk_insert_mappings = bulk_update_mappings = _deny


@contextmanager
def read_authority(db, actor, company, identity, permission_rows):
    from app.access.models import AccessPolicy, AccessMembership, AccessRole
    from app.models.user import User, Role
    from app.common.models import CommonPerson
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.shared.models import ServicePolicy
    from app.models.user import Permission
    from app.branches.models import BranchOwnership
    from app.business_packs.common_queries import assert_mapped_sources

    if type(company) is not int or company <= 0 or identity['id'] != actor.id:
        raise HTTPException(403, 'An exact AI actor/company authority snapshot is required')
    connection = db.connection()
    policy_table = ServicePolicy.__table__
    legacy_policy = company == 1
    if inspect(connection).has_table(BranchOwnership.__tablename__):
        owner = BranchOwnership.__table__
        key = (owner.c.resource_table == policy_table.name,
            owner.c.resource_key == cast(policy_table.c.id, String))
        approved = exists(select(1).where(*key, owner.c.company_id == company)).correlate(policy_table)
        legacy_policy = or_(approved, ~exists(select(1).where(*key)).correlate(policy_table)) if company == 1 else approved
    conditions = {
        AccessPolicy: and_(AccessPolicy.user_id == actor.id, AccessPolicy.company_id == company),
        AccessMembership: and_(AccessMembership.user_id == actor.id, AccessMembership.company_id == company),
        AccessRole: AccessRole.company_id == company,
        Permission: Permission.id.is_not(None),
        ServicePolicy: and_(ServicePolicy.scope_key == f'company:{company}:ai_security',
            ServicePolicy.kind == 'ai_security',
            or_(ServicePolicy.organization_id == company,
                and_(ServicePolicy.organization_id.is_(None), legacy_policy))),
    }
    options = tuple(with_loader_criteria(model, criterion, include_aliases=True,
        propagate_to_loaders=False) for model, criterion in conditions.items())
    snapshot = _ReadOnlyAuthority(bind=connection, autoflush=False, expire_on_commit=False,
        join_transaction_mode='rollback_only')

    def deny(*args, **kwargs):
        raise HTTPException(403, 'AI authority snapshots are read-only')

    def restrict(execution):
        if (not execution.is_orm_statement or execution.is_insert or execution.is_update or execution.is_delete
                or execution.bind_mapper is not None and execution.bind_mapper.class_ not in conditions):
            deny()
        assert_mapped_sources(execution.statement, set(conditions))
        execution.statement = execution.statement.options(*options)
        execution.update_execution_options(compiled_cache=None)

    event.listen(snapshot, 'do_orm_execute', restrict)
    event.listen(snapshot, 'before_flush', deny)
    try:
        role_name = connection.scalar(select(Role.__table__.c.name).where(Role.__table__.c.id == identity['role_id']))
        person_company = connection.scalar(select(CommonPerson.__table__.c.organization_id).where(
            CommonPerson.__table__.c.user_id == actor.id))
        view = SimpleNamespace(id=actor.id, role_id=identity['role_id'], is_superuser=identity['is_superuser'],
            is_active=identity['is_active'], organization_id=company,
            role=SimpleNamespace(name=role_name, permissions=[SimpleNamespace(**dict(row)) for row in permission_rows]) if role_name else None,
            person=SimpleNamespace(organization_id=person_company) if person_company else None, employee=None)
        from app.access import service
        policy = service.policy_for(snapshot, view, company)
        if policy is None or not person_company:
            # Keep canonical tenant/branch/private row predicates on the original
            # session. Only own employment metadata needed by legacy intern and
            # primary-company rules is projected; never load salary/profile bodies.
            with db.no_autoflush:
                employees = db.query(Employee.id, Employee.employment_type, Employee.branch_id).filter(
                    Employee.user_id == actor.id, Employee.deleted_at.is_(None)).limit(2).all()
            if len(employees) > 1:
                raise HTTPException(403, 'AI actor canonical employment is ambiguous')
            if employees:
                employee = employees[0]
                branch_company = connection.scalar(select(Branch.__table__.c.company_id).where(
                    Branch.__table__.c.id == employee.branch_id)) if employee.branch_id is not None else None
                if employee.branch_id is not None and branch_company != company:
                    raise HTTPException(403, 'AI actor employment company changed')
                view.employee = SimpleNamespace(employment_type=employee.employment_type,
                    branch=SimpleNamespace(company_id=branch_company) if branch_company else None)
        yield snapshot, view, policy
    finally:
        # This session joins the caller's actual connection read-only. close()
        # must not commit or roll back its externally owned transaction.
        snapshot.close()
