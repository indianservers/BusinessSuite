"""Tenant guards for legacy shared-service APIs, including unmanaged accounts.

The new governance APIs apply their own explicit tenant/authority checks. Old
automation APIs cannot edit versioned definitions through their mutable routes.
"""

from fastapi import HTTPException
from sqlalchemy import event, func, select, and_, or_
from sqlalchemy.orm import with_loader_criteria
from app.db.base_class import Base


def install(db, company, module):
    if module not in {"automation", "communication", "approvals"}:
        return lambda: None
    models = {
        mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers
    }
    clauses = {}
    for model in models.values():
        source = model.__module__
        if not (
            source.startswith("app.apps.automation.")
            or source.startswith("app.apps.communication.")
            or source in {"app.models.approval_os", "app.models.workflow_engine"}
        ):
            continue
        columns = model.__table__.c
        clause = None
        if "organization_id" in columns:
            clause = func.coalesce(model.organization_id, 1) == company
        else:
            parents = []
            for column in columns:
                for fk in column.foreign_keys:
                    parent = fk.column.table
                    if "organization_id" in parent.c:
                        parent_clause = (
                            func.coalesce(parent.c.organization_id, 1) == company
                        )
                        if parent.name == "automation_workflows":
                            parent_clause = and_(
                                parent_clause, parent.c.graph_json.is_(None)
                            )
                        access = column.in_(select(fk.column).where(parent_clause))
                        parents.append(
                            or_(column.is_(None), access) if column.nullable else access
                        )
            if parents:
                clause = and_(*parents)
        if model.__tablename__ == "automation_workflows":
            clause = and_(clause, model.graph_json.is_(None))
        if clause is not None:
            clauses[model] = clause
    options = [
        with_loader_criteria(model, clause, include_aliases=True)
        for model, clause in clauses.items()
    ]

    def restrict(execution):
        if execution.is_select or execution.is_update or execution.is_delete:
            execution.statement = execution.statement.options(*options)

    def validate(session, *args):
        for item in session.new | session.dirty | session.deleted:
            if type(item) not in clauses:
                continue
            if hasattr(item, "organization_id"):
                if item in session.new and item.organization_id is None:
                    item.organization_id = company
                if (item.organization_id or 1) != company:
                    raise HTTPException(
                        403, "Cross-company shared-service write denied"
                    )
            if (
                item.__tablename__ == "automation_workflows"
                and item.graph_json is not None
            ):
                raise HTTPException(409, "Use the versioned shared workflow builder")

    event.listen(db, "do_orm_execute", restrict)
    event.listen(db, "before_flush", validate)
    original_get = db.get

    def get(model, ident, **kwargs):
        if model in clauses:
            with db.no_autoflush:
                row = db.query(model).filter(model.id == ident, clauses[model]).first()
            return row
        return original_get(model, ident, **kwargs)

    db.get = get

    def cleanup():
        db.get = original_get
        event.remove(db, "do_orm_execute", restrict)
        event.remove(db, "before_flush", validate)

    return cleanup
