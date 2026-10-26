"""Bounded, scoped server-side analytics over existing domain tables."""

from contextlib import contextmanager
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import func
from app.access import service
from app.access.scope import install_scope
from app.shared.contracts import authorize
from app.apps.crm.models import CRMLead, CRMDeal
from app.apps.project_management.models import PMSProject, PMSTask
from app.apps.srm.models import SRMInvoice
from app.models.employee import Employee
from app.models.company import Branch

SOURCES = {
    "crm_leads": ("crm", CRMLead, "crm_view", "/crm/leads"),
    "crm_pipeline": ("crm", CRMDeal, "crm_view", "/crm/pipeline"),
    "projects": ("project_management", PMSProject, "pms_view", "/pms/projects"),
    "tasks": ("project_management", PMSTask, "pms_view", "/pms/tasks"),
    "invoices": ("srm", SRMInvoice, "srm_view", "/srm/invoices"),
    "employees": ("hrms", Employee, "employee_view", "/hrms/employees"),
}


@contextmanager
def scoped(db, actor, company, module):
    saved = {
        k: v
        for k, v in actor.__dict__.items()
        if k.startswith("_suite_") or k == "organization_id"
    }
    policy = service.policy_for(db, actor, company)
    if not actor.is_superuser and not policy:
        raise HTTPException(403, "Analytics requires an explicit managed access policy")
    from app.access.catalog import catalog, ACTIONS

    grants = (
        service.resolved_grants(db, policy)
        if not actor.is_superuser
        else {
            m["key"]: {
                "enabled": True,
                "actions": list(ACTIONS),
                "scope": "organization",
                "permissions": [p["name"] for p in m["permissions"]],
            }
            for m in catalog(db)
        }
    )
    actor.organization_id = company
    actor._suite_current_module = module
    cleanup = install_scope(db, actor, company, grants)
    try:
        yield
    finally:
        cleanup()
        for k in list(actor.__dict__):
            if k.startswith("_suite_") or k == "organization_id":
                actor.__dict__.pop(k, None)
        actor.__dict__.update(saved)


def aggregate(
    db, actor, company, key, start=None, end=None, branch=None, department=None
):
    if key not in SOURCES:
        raise HTTPException(422, "Unknown analytics source")
    module, model, permission, path = SOURCES[key]
    authorize(db, actor, company, module, "view", permission)
    from app.enterprise.controls import governance_check

    entities = {
        "crm_leads": "lead",
        "crm_pipeline": "deal",
        "projects": "project",
        "tasks": "task",
        "invoices": "invoice",
        "employees": "employee",
    }
    governance_check(db, actor, company, module, entities[key])
    if start and end and end < start:
        raise HTTPException(422, "End date precedes start date")
    with scoped(db, actor, company, module):
        filters = []
        if hasattr(model, "organization_id"):
            filters.append(func.coalesce(model.organization_id, 1) == company)
        elif model is Employee:
            filters.append(
                Employee.branch_id.in_(
                    db.query(Branch.id).filter(Branch.company_id == company)
                )
            )
        if hasattr(model, "deleted_at"):
            filters.append(model.deleted_at.is_(None))
        for name, value in (("branch_id", branch), ("department_id", department)):
            if value is not None:
                if not hasattr(model, name):
                    raise HTTPException(
                        422, f"{key} does not support the {name} filter"
                    )
                filters.append(getattr(model, name) == value)
        if start:
            filters.append(model.created_at >= start)
        if end:
            filters.append(model.created_at <= end)
        total = (
            db.query(func.count(model.id)).select_from(model).filter(*filters).scalar()
        )
        status = getattr(model, "status", None)
        groups = (
            [
                {"label": str(label or "Unspecified"), "count": count}
                for label, count in db.query(status, func.count(model.id))
                .select_from(model)
                .filter(*filters)
                .group_by(status)
                .order_by(func.count(model.id).desc())
                .limit(50)
            ]
            if status is not None
            else []
        )
        amounts = []
        if key in {"crm_pipeline", "invoices"}:
            field = model.amount if key == "crm_pipeline" else model.total_amount
            query = (
                db.query(model.currency, func.sum(field))
                .select_from(model)
                .filter(*filters)
                .group_by(model.currency)
            )
            amounts = [
                {"currency": currency, "amount": str(amount or 0)}
                for currency, amount in query.limit(30)
            ]
        date = func.date(model.created_at)
        series = [
            {"date": str(day), "count": count}
            for day, count in db.query(date, func.count(model.id))
            .select_from(model)
            .filter(*filters)
            .group_by(date)
            .order_by(date.desc())
            .limit(60)
        ]
        return {
            "series": list(reversed(series)),
            "key": key,
            "module": module,
            "count": total,
            "groups": groups,
            "amounts": amounts,
            "path": path,
            "scope": "current effective record scope",
            "filters": {
                "start": start,
                "end": end,
                "branch": branch,
                "department": department,
            },
        }
