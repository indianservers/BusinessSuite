"""Licensing and flag decisions only narrow existing authorization."""

import hashlib
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import inspect, select, func
from app.apps.saas.models import TenantSubscription, TenantSubscriptionPlan
from app.apps.business_os.models import BOSFeatureFlag


def subscription(db, company):
    if "company_id" not in {
        c["name"] for c in inspect(db.connection()).get_columns("tenant_subscriptions")
    }:
        return None
    s, p = TenantSubscription.__table__, TenantSubscriptionPlan.__table__
    row = (
        db.connection()
        .execute(select(s).where(s.c.company_id == company))
        .mappings()
        .first()
    )
    if not row:
        return None
    plan = (
        db.connection()
        .execute(select(p).where(p.c.id == row["plan_id"]))
        .mappings()
        .first()
    )
    if not plan:
        raise HTTPException(403, "Assigned subscription plan is unavailable")
    values = dict(plan["config_json"] or {})
    values.update(row["config_json"] or {})
    pending = values.get("scheduled_change")
    if pending and datetime.fromisoformat(pending["effective_at"]).astimezone(
        timezone.utc
    ) <= datetime.now(timezone.utc):
        target = (
            db.connection()
            .execute(select(p).where(p.c.id == pending["plan_id"]))
            .mappings()
            .first()
        )
        if target:
            values = {**values, **(target["config_json"] or {})}
    return {
        "id": row["id"],
        "planId": plan["id"],
        "plan": plan["name"],
        "status": row["status"],
        "version": row["version"],
        "values": values,
    }


def disabled_modules(db, company):
    row = subscription(db, company)
    if not row or not row["values"].get("enforce", False):
        return set()
    from app.access.catalog import MODULES

    values = row["values"]
    if row["status"] == "suspended":
        return set(MODULES)
    if (
        values.get("expiry_policy") == "restrict"
        and values.get("grace_until")
        and datetime.fromisoformat(values["grace_until"]).astimezone(timezone.utc)
        < datetime.now(timezone.utc)
    ):
        return set(MODULES)
    return set(MODULES) - set(values.get("modules", []))


def evaluate_flag(db, user, company, module, key):
    from app.shared.contracts import authorize

    authorize(db, user, company, module)
    from app.core.config import settings

    table = BOSFeatureFlag.__table__
    row = (
        db.connection()
        .execute(
            select(table).where(
                table.c.company_id == company,
                table.c.module_key == module,
                table.c.flag_key == key,
            )
        )
        .mappings()
        .first()
    )
    if not row or not row["enabled"]:
        return {"enabled": False, "reason": "disabled_or_unconfigured"}
    data = row["value_json"] or {}
    if data.get("environment", "production") != settings.ENVIRONMENT:
        return {"enabled": False, "reason": "environment"}
    if data.get("expires_at") and datetime.fromisoformat(data["expires_at"]).astimezone(
        timezone.utc
    ) <= datetime.now(timezone.utc):
        return {"enabled": False, "reason": "expired"}
    branch = getattr(getattr(user, "employee", None), "branch_id", None)
    for field, actual in (
        ("users", user.id),
        ("branches", branch),
        ("roles", user.role_id),
    ):
        if data.get(field) and actual not in data[field]:
            return {"enabled": False, "reason": "targeting"}
    bucket = (
        int(
            hashlib.sha256(f"{company}:{module}:{key}:{user.id}".encode()).hexdigest()[
                :8
            ],
            16,
        )
        % 10000
    )
    return {
        "enabled": bucket < int(data.get("percentage", 100)) * 100,
        "reason": "stable_rollout",
        "version": data.get("version", 1),
    }


def governance_check(db, user, company, module, entity, destructive=False):
    from app.shared.models import ServicePolicy

    table = ServicePolicy.__table__
    data = (
        db.connection()
        .execute(
            table.select().where(
                table.c.scope_key == f"company:{company}:governance:{module}:{entity}",
                table.c.kind == "governance",
            )
        )
        .mappings()
        .first()
    )
    if not data:
        return
    values = data["values_json"] or {}
    if destructive and values.get("legalHold"):
        raise HTTPException(409, "Record type is subject to an active legal hold")
    if (
        values.get("classification") == "restricted"
        and not user.is_superuser
        and user.role_id not in values.get("allowedRoles", [])
    ):
        raise HTTPException(
            403, "Restricted data classification requires an authorized role"
        )


def quota(db, company, metric, additional=1):
    """Company-serialized limits for shared-service consumption; legacy APIs are separate."""
    row = subscription(db, company)
    if not row or not row["values"].get("enforce"):
        return
    limit = row["values"].get(metric)
    if limit is None:
        return
    from app.models.company import Company
    from sqlalchemy import select

    db.connection().execute(
        select(Company.__table__.c.id)
        .where(Company.__table__.c.id == company)
        .with_for_update()
    )
    beginning = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    if metric == "seats":
        used = active_seats(db, company)
        maximum = limit
    elif metric == "storage_mb":
        from app.shared.models import ServiceDocument

        table = ServiceDocument.__table__
        used = (
            db.connection()
            .execute(
                select(func.coalesce(func.sum(table.c.size_bytes), 0)).where(
                    table.c.organization_id == company
                )
            )
            .scalar()
        )
        maximum = limit * 1024 * 1024
    elif metric == "ai_requests":
        from app.ai_agents.models import AiUsageEvent

        table = AiUsageEvent.__table__
        used = (
            db.connection()
            .execute(
                select(func.count())
                .select_from(table)
                .where(
                    table.c.company_id == company,
                    table.c.event_type == "shared_request",
                    table.c.created_at >= beginning,
                )
            )
            .scalar()
        )
        maximum = limit
    elif metric == "automation_runs":
        from app.apps.automation.models import AutomationScheduledJob

        table = AutomationScheduledJob.__table__
        used = (
            db.connection()
            .execute(
                select(func.count())
                .select_from(table)
                .where(
                    table.c.organization_id == company,
                    table.c.job_type == "shared_workflow",
                    table.c.created_at >= beginning,
                )
            )
            .scalar()
        )
        maximum = limit
    else:
        return
    if used + additional > maximum:
        raise HTTPException(429, f"Company subscription {metric} quota exceeded")


def company_user_ids(db, company, active_only=False):
    from app.models.user import User
    from app.common.models import CommonPerson
    from app.models.employee import Employee
    from app.models.company import Branch
    from app.access.models import AccessMembership
    from sqlalchemy import or_

    u, p, e, b, m = [
        model.__table__
        for model in (User, CommonPerson, Employee, Branch, AccessMembership)
    ]
    source = (
        u.outerjoin(p, p.c.user_id == u.c.id)
        .outerjoin(e, e.c.user_id == u.c.id)
        .outerjoin(b, b.c.id == e.c.branch_id)
    )
    member = select(m.c.user_id).where(m.c.company_id == company, m.c.active.is_(True))
    query = (
        select(u.c.id)
        .select_from(source)
        .where(
            or_(
                func.coalesce(p.c.organization_id, b.c.company_id, 1) == company,
                u.c.id.in_(member),
            )
        )
    )
    if active_only:
        query = query.where(u.c.is_active.is_(True))
    return query.distinct()


def active_seats(db, company):
    return (
        db.connection()
        .execute(
            select(func.count()).select_from(
                company_user_ids(db, company, True).subquery()
            )
        )
        .scalar()
    )


def governance_module_check(db, user, company, module, action="view"):
    if not module:
        return
    from app.shared.models import ServicePolicy

    table = ServicePolicy.__table__
    if not inspect(db.connection()).has_table(table.name):
        return
    rows = (
        db.connection()
        .execute(
            select(table.c.values_json).where(
                table.c.organization_id == company, table.c.kind == "governance"
            )
        )
        .scalars()
    )
    for values in rows:
        values = values or {}
        if values.get("module") != module:
            continue
        if action == "delete" and values.get("legalHold"):
            raise HTTPException(
                409, "Active governance hold blocks destructive module operations"
            )
        if (
            values.get("classification") == "restricted"
            and not user.is_superuser
            and user.role_id not in values.get("allowedRoles", [])
        ):
            raise HTTPException(
                403, "Restricted governance policy requires an authorized module role"
            )


def reserve_api_request(db, user, company, module):
    if not module:
        return
    row = subscription(db, company)
    if (
        not row
        or not row["values"].get("enforce")
        or row["values"].get("api_requests") is None
    ):
        return
    from app.models.company import Company
    from app.shared.models import ServicePolicy

    db.query(Company).filter_by(id=company).with_for_update().one()
    period = datetime.now(timezone.utc).strftime("%Y-%m")
    key = f"company:{company}:api_usage:{period}"
    counter = (
        db.query(ServicePolicy)
        .filter_by(scope_key=key, kind="api_usage")
        .with_for_update()
        .first()
    )
    used = (counter.values_json or {}).get("count", 0) if counter else 0
    if used >= row["values"]["api_requests"]:
        raise HTTPException(429, "Company subscription API request quota exceeded")
    if not counter:
        counter = ServicePolicy(
            scope_key=key,
            organization_id=company,
            kind="api_usage",
            version=0,
            updated_by=user.id,
        )
        db.add(counter)
    counter.values_json = {
        "count": used + 1,
        "period": period,
        "unit": "authenticated business API attempts",
    }
    counter.version += 1
    counter.updated_by = user.id
    # Authentication has completed, and no endpoint business mutation has started.
    # Reserve durably before releasing the company lock; failed attempts still count.
    db.commit()


def usage_snapshot(db, company):
    from app.shared.models import ServiceDocument, ServicePolicy
    from app.ai_agents.models import AiUsageEvent
    from app.apps.automation.models import AutomationScheduledJob

    beginning = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    document, ai, job, policy = [
        model.__table__
        for model in (
            ServiceDocument,
            AiUsageEvent,
            AutomationScheduledJob,
            ServicePolicy,
        )
    ]
    storage = (
        db.connection()
        .execute(
            select(func.coalesce(func.sum(document.c.size_bytes), 0)).where(
                document.c.organization_id == company
            )
        )
        .scalar()
    )
    requests = (
        db.connection()
        .execute(
            select(func.count())
            .select_from(ai)
            .where(
                ai.c.company_id == company,
                ai.c.event_type == "shared_request",
                ai.c.created_at >= beginning,
            )
        )
        .scalar()
    )
    runs = (
        db.connection()
        .execute(
            select(func.count())
            .select_from(job)
            .where(
                job.c.organization_id == company,
                job.c.job_type == "shared_workflow",
                job.c.created_at >= beginning,
            )
        )
        .scalar()
    )
    period = beginning.strftime("%Y-%m")
    value = (
        db.connection()
        .execute(
            select(policy.c.values_json).where(
                policy.c.scope_key == f"company:{company}:api_usage:{period}",
                policy.c.kind == "api_usage",
            )
        )
        .scalar()
    )
    return {
        "period": period,
        "storageBytes": int(storage),
        "aiRequests": requests,
        "automationRuns": runs,
        "apiRequests": (value or {}).get("count", 0),
    }
