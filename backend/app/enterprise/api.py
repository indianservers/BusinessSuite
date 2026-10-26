"""Enterprise administration over existing plans, flags, policies and helpdesk."""

import copy, csv, io, json, re, uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import Response
from pydantic import Field
from sqlalchemy import func, inspect
from sqlalchemy.orm import Session
from app.access.api import Strict, admin, company_access, serialize, users_in_company
from app.access.control import mutate, record
from app.access import service
from app.access.catalog import catalog
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.company import Company, Branch, Department
from app.models.helpdesk import HelpdeskTicket, HelpdeskReply
from app.apps.saas.models import TenantSubscriptionPlan, TenantSubscription
from app.apps.business_os.models import BOSFeatureFlag, BOSEntityLink
from app.shared.models import ServicePolicy
from app.shared.contracts import authorize, RECORDS
from app.enterprise.controls import (
    subscription,
    evaluate_flag,
    active_seats,
    company_user_ids,
)
from app.enterprise.analytics import aggregate, SOURCES
from app.enterprise.operations import health, errors

router = APIRouter(prefix="/access/enterprise", tags=["Enterprise Control Center"])


def change(db, actor, company, request, global_only=False):
    company_access(db, actor, company)
    if global_only and not actor.is_superuser:
        raise HTTPException(403, "Global Super Admin required")
    mutate(request, actor)
    db.query(Company).filter_by(id=company).with_for_update().one()


def audit(db, actor, company, operation, reason, request, after=None):
    record(
        db,
        actor,
        company,
        "enterprise." + operation,
        {"reason": reason, **(after or {})},
        request,
    )


class Command(Strict):
    companyId: int = Field(gt=0)
    version: int = Field(default=0, ge=0)
    reason: str = Field(min_length=3, max_length=500)


@router.get("/catalog")
def enterprise_catalog(db: Session = Depends(get_db), actor: User = Depends(admin)):
    return {
        "modules": [
            {
                "key": m["key"],
                "label": m["label"],
                "installed": m["installed"],
                "authentication": "central",
                "entitlements": "backend enforced",
                "recordAdapters": [
                    entity for (module, entity) in RECORDS if module == m["key"]
                ],
                "analytics": [
                    key for key, source in SOURCES.items() if source[0] == m["key"]
                ],
                "securityVerification": "See regression coverage report; not every domain route is certified",
            }
            for m in catalog(db)
        ],
        "backup": "existing data-backups service",
        "billing": "not connected; no payment collection",
        "support": "existing helpdesk tickets",
    }


@router.get("/analytics")
def analytics(
    companyId: int = 1,
    source: str = "crm_leads",
    start: datetime | None = None,
    end: datetime | None = None,
    branchId: int | None = None,
    departmentId: int | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    return aggregate(db, actor, companyId, source, start, end, branchId, departmentId)


@router.get("/analytics/export")
def export_analytics(
    request: Request,
    companyId: int = 1,
    source: str = "crm_leads",
    start: datetime | None = None,
    end: datetime | None = None,
    branchId: int | None = None,
    departmentId: int | None = None,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    if source not in SOURCES:
        raise HTTPException(422, "Unknown source")
    authorize(db, actor, companyId, SOURCES[source][0], "export", SOURCES[source][2])
    data = aggregate(db, actor, companyId, source, start, end, branchId, departmentId)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["source", "group", "count"])
    for group in data["groups"] or [{"label": "Total", "count": data["count"]}]:
        label = group["label"]
        writer.writerow(
            [
                source,
                (
                    "'" + label
                    if label.startswith(("=", "+", "-", "@", "\t", "\r"))
                    else label
                ),
                group["count"],
            ]
        )
    audit(
        db,
        actor,
        companyId,
        "analytics.export",
        "Export authorized aggregate report",
        request,
        {"source": source},
    )
    db.commit()
    return Response(
        out.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=enterprise-report.csv",
            "Cache-Control": "no-store",
        },
    )


@router.get("/plans")
def plans(db: Session = Depends(get_db), actor: User = Depends(admin)):
    return [
        serialize(row)
        for row in db.query(TenantSubscriptionPlan)
        .order_by(TenantSubscriptionPlan.name)
        .limit(100)
    ]


class PlanInput(Command):
    code: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,59}$")
    name: str = Field(min_length=2, max_length=120)
    modules: list[str] = Field(max_length=100)
    active: bool = True
    seats: int = Field(ge=1, le=1000000)
    storageMb: int = Field(ge=1, le=100000000)
    aiRequests: int = Field(ge=0, le=100000000)
    automationRuns: int = Field(ge=0, le=100000000)
    apiRequests: int = Field(ge=0, le=100000000)
    supportLevel: str = Field(default="standard", max_length=80)
    billingInterval: Literal["monthly", "yearly", "custom"] = "monthly"


@router.post("/plans")
def save_plan(
    data: PlanInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request, True)
    known = {m["key"] for m in catalog(db)}
    if set(data.modules) - known:
        raise HTTPException(422, "Unknown plan module")
    row = (
        db.query(TenantSubscriptionPlan)
        .filter_by(code=data.code)
        .with_for_update()
        .first()
    )
    if row and row.version != data.version or not row and data.version:
        raise HTTPException(409, "Plan version changed")
    if not row:
        row = TenantSubscriptionPlan(code=data.code, version=0)
        db.add(row)
    row.name, row.active = data.name, data.active
    row.config_json = {
        "modules": sorted(set(data.modules)),
        "seats": data.seats,
        "storage_mb": data.storageMb,
        "ai_requests": data.aiRequests,
        "automation_runs": data.automationRuns,
        "api_requests": data.apiRequests,
        "support_level": data.supportLevel,
        "billing_interval": data.billingInterval,
    }
    row.version += 1
    audit(
        db,
        actor,
        data.companyId,
        "plan.saved",
        data.reason,
        request,
        {"code": row.code, "version": row.version},
    )
    db.commit()
    return serialize(row)


@router.get("/subscription")
def get_subscription(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    row = subscription(db, companyId)
    from app.enterprise.controls import usage_snapshot

    return {
        "usage": usage_snapshot(db, companyId),
        "subscription": row,
        "activeSeats": active_seats(db, companyId),
        "billing": "not connected",
        "quotaEnforcement": {
            "modules": "enforced",
            "seats": "assignment validation",
            "storage": "shared documents",
            "ai": "shared gateway",
            "automation": "shared workflows",
            "api": "authenticated business API attempts per UTC month",
        },
    }


class SubscriptionInput(Command):
    planId: int = Field(gt=0)
    status: Literal["active", "trial", "grace", "suspended"] = "active"
    renewalAt: datetime | None = None
    graceUntil: datetime | None = None
    expiryPolicy: Literal["allow", "restrict"] = "allow"
    scheduledPlanId: int | None = None
    effectiveAt: datetime | None = None


@router.put("/subscription")
def save_subscription(
    data: SubscriptionInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request, True)
    for timestamp in (data.renewalAt, data.graceUntil, data.effectiveAt):
        if timestamp and timestamp.tzinfo is None:
            raise HTTPException(
                422, "Subscription dates require an explicit UTC offset"
            )
    plan = db.get(TenantSubscriptionPlan, data.planId)
    if not plan or not plan.active:
        raise HTTPException(422, "Choose an active plan")
    seats = (plan.config_json or {}).get("seats")
    if seats and active_seats(db, data.companyId) > seats:
        raise HTTPException(
            409, "Active seats exceed the selected plan; adjust membership first"
        )
    if data.expiryPolicy == "restrict" and (
        not data.graceUntil or not data.renewalAt or data.graceUntil < data.renewalAt
    ):
        raise HTTPException(
            422, "Restrictive expiry requires renewal and grace dates in order"
        )
    row = (
        db.query(TenantSubscription)
        .filter_by(company_id=data.companyId)
        .with_for_update()
        .first()
    )
    if row and row.version != data.version or not row and data.version:
        raise HTTPException(409, "Subscription version changed")
    if not row:
        row = TenantSubscription(company_id=data.companyId, version=0)
        db.add(row)
    values = {
        "enforce": True,
        "renewal_at": data.renewalAt.isoformat() if data.renewalAt else None,
        "grace_until": data.graceUntil.isoformat() if data.graceUntil else None,
        "expiry_policy": data.expiryPolicy,
    }
    if data.scheduledPlanId:
        target = db.get(TenantSubscriptionPlan, data.scheduledPlanId)
        if (
            not target
            or not target.active
            or not data.effectiveAt
            or data.effectiveAt.astimezone(timezone.utc) <= datetime.now(timezone.utc)
        ):
            raise HTTPException(
                422, "Scheduled change requires an active plan and future time"
            )
        values["scheduled_change"] = {
            "plan_id": target.id,
            "effective_at": data.effectiveAt.isoformat(),
        }
    row.plan_id, row.status, row.admin_override, row.config_json = (
        data.planId,
        data.status,
        False,
        values,
    )
    row.version += 1
    audit(
        db,
        actor,
        data.companyId,
        "subscription.saved",
        data.reason,
        request,
        {"planId": plan.id, "version": row.version},
    )
    db.commit()
    return serialize(row)


class FlagInput(Command):
    module: str
    key: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,119}$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    ownerId: int = Field(gt=0)
    enabled: bool = False
    environment: Literal["development", "test", "staging", "production"] = "production"
    percentage: int = Field(default=100, ge=0, le=100)
    users: list[int] = Field(default_factory=list, max_length=1000)
    branches: list[int] = Field(default_factory=list, max_length=1000)
    roles: list[int] = Field(default_factory=list, max_length=1000)
    expiresAt: datetime | None = None


@router.get("/flags")
def flags(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return [
        serialize(row)
        for row in db.query(BOSFeatureFlag)
        .filter_by(company_id=companyId)
        .order_by(BOSFeatureFlag.id)
        .limit(200)
    ]


@router.put("/flags")
def save_flag(
    data: FlagInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    if data.module not in {m["key"] for m in catalog(db)}:
        raise HTTPException(422, "Unknown module")
    members = set(
        db.connection().execute(company_user_ids(db, data.companyId)).scalars()
    )
    if data.ownerId not in members or not set(data.users) <= members:
        raise HTTPException(422, "Flag users must belong to the company")
    branches = {b.id for b in db.query(Branch).filter_by(company_id=data.companyId)}
    if not set(data.branches) <= branches:
        raise HTTPException(422, "Branch is outside company")
    row = (
        db.query(BOSFeatureFlag)
        .filter_by(company_id=data.companyId, module_key=data.module, flag_key=data.key)
        .with_for_update()
        .first()
    )
    version = (row.value_json or {}).get("version", 0) if row else 0
    if data.version != version:
        raise HTTPException(409, "Flag version changed")
    if not row:
        row = BOSFeatureFlag(
            company_id=data.companyId, module_key=data.module, flag_key=data.key
        )
        db.add(row)
    previous_enabled = bool(row.enabled)
    row.enabled = data.enabled
    row.value_json = {
        "name": data.name,
        "description": data.description,
        "ownerId": data.ownerId,
        "environment": data.environment,
        "percentage": data.percentage,
        "users": data.users,
        "branches": data.branches,
        "roles": data.roles,
        "expires_at": data.expiresAt.isoformat() if data.expiresAt else None,
        "version": version + 1,
        "previous": {
            "enabled": previous_enabled,
            "config": {
                k: v for k, v in (row.value_json or {}).items() if k != "previous"
            },
        },
    }
    audit(
        db,
        actor,
        data.companyId,
        "flag.saved",
        data.reason,
        request,
        {"module": data.module, "key": data.key, "version": version + 1},
    )
    db.commit()
    return serialize(row)


@router.get("/flags/evaluate")
def flag_decision(
    module: str,
    key: str,
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return evaluate_flag(db, actor, companyId, module, key)


@router.get("/health")
def system_health(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    return health(db, actor, companyId)


@router.get("/errors")
def error_center(
    companyId: int = 1,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    return errors(db, actor, companyId, page)


class PolicyInput(Command):
    key: str = Field(pattern=r"^[a-zA-Z0-9_.:-]{1,180}$")
    kind: Literal[
        "branding",
        "dashboard",
        "governance",
        "error_resolution",
        "recovery_request",
        "support_access_request",
    ]
    values: dict


def validate_policy(data):
    values = data.values
    if len(json.dumps(values)) > 20000:
        raise HTTPException(422, "Configuration is too large")
    allowed = {
        "branding": {
            "appName",
            "primary",
            "surface",
            "background",
            "text",
            "radius",
            "logoPath",
            "emailFooter",
            "documentFooter",
            "domain",
        },
        "dashboard": {"name", "widgets", "sharedRoles"},
        "governance": {
            "module",
            "entity",
            "classification",
            "ownerId",
            "retentionDays",
            "legalBasis",
            "legalHold",
            "allowedRoles",
        },
        "error_resolution": {"status", "notes"},
        "recovery_request": {
            "backupId",
            "environment",
            "procedure",
            "status",
            "verification",
        },
        "support_access_request": {"userId", "expiresAt", "status", "purpose"},
    }[data.kind]
    if set(values) - allowed:
        raise HTTPException(422, "Unknown configuration field")
    if data.kind == "branding":
        if "appName" in values and (
            not isinstance(values["appName"], str)
            or not 1 <= len(values["appName"]) <= 80
        ):
            raise HTTPException(422, "Application name must be 1–80 characters")
        for color in ("primary", "surface", "background", "text"):
            if color in values and (
                not isinstance(values[color], str)
                or not re.fullmatch(r"#[0-9a-fA-F]{6}", values[color])
            ):
                raise HTTPException(422, "Use six-digit hex colors")

        def luminance(color):
            channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
            channels = [
                v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
                for v in channels
            ]
            return sum(v * w for v, w in zip(channels, (0.2126, 0.7152, 0.0722)))

        if "primary" in values and (1.05 / (luminance(values["primary"]) + 0.05)) < 4.5:
            raise HTTPException(
                422, "Primary accent requires 4.5:1 contrast with white button text"
            )
        for back in (
            values.get("surface", "#ffffff"),
            values.get("background", "#ffffff"),
        ):
            a, b = sorted([luminance(values.get("text", "#171717")), luminance(back)])
            if (b + 0.05) / (a + 0.05) < 4.5:
                raise HTTPException(422, "Text contrast must be at least 4.5:1")
        if "radius" in values and (
            type(values["radius"]) is not int or not 0 <= values["radius"] <= 20
        ):
            raise HTTPException(422, "Radius must be 0–20 pixels")
        if values.get("logoPath") and not re.fullmatch(
            r"/uploads/[a-zA-Z0-9_./-]+", values["logoPath"]
        ):
            raise HTTPException(422, "Logo must be a managed upload path")
        if values.get("logoPath") and ".." in values["logoPath"]:
            raise HTTPException(422, "Unsafe logo path")
        for field in ("emailFooter", "documentFooter", "domain"):
            if field in values and (
                not isinstance(values[field], str) or len(values[field]) > 1000
            ):
                raise HTTPException(422, "Invalid branding text")
    elif data.kind == "governance":
        if values.get("classification") not in (
            "public",
            "internal",
            "confidential",
            "restricted",
        ):
            raise HTTPException(422, "Choose a classification")
        if type(values.get("legalHold", False)) is not bool:
            raise HTTPException(422, "Legal hold must be boolean")
        if values.get("retentionDays") is not None and (
            type(values["retentionDays"]) is not int
            or values["retentionDays"] < 1
            or not values.get("legalBasis")
        ):
            raise HTTPException(
                422, "Retention needs positive days and a verified policy reference"
            )
        if not isinstance(values.get("allowedRoles", []), list) or any(
            type(v) is not int for v in values.get("allowedRoles", [])
        ):
            raise HTTPException(422, "Roles must be numeric IDs")
        if (
            not isinstance(values.get("module"), str)
            or not isinstance(values.get("entity"), str)
            or (values.get("module"), values.get("entity")) not in RECORDS
        ):
            raise HTTPException(422, "Register an entity adapter before governing it")
    elif data.kind == "error_resolution":
        if values.get("status") not in ("open", "acknowledged", "resolved"):
            raise HTTPException(422, "Invalid error state")
    elif data.kind == "dashboard":
        if not isinstance(values.get("sharedRoles", []), list) or any(
            type(role) is not int for role in values.get("sharedRoles", [])
        ):
            raise HTTPException(422, "Shared roles must be numeric role IDs")
        if (
            not isinstance(values.get("name"), str)
            or not 1 <= len(values["name"]) <= 180
        ):
            raise HTTPException(422, "Dashboard name must be 1–180 characters")
        widgets = values.get("widgets", [])
        if not isinstance(widgets, list) or len(widgets) > 24:
            raise HTTPException(422, "Dashboard allows up to 24 widgets")
        for widget in widgets:
            if (
                not isinstance(widget, dict)
                or set(widget) - {"source", "type", "width", "title"}
                or not isinstance(widget.get("source"), str)
                or widget.get("source") not in SOURCES
                or widget.get("type")
                not in ("kpi", "table", "bar", "line", "donut", "funnel", "trend")
                or widget.get("width", 1) not in (1, 2, 3)
            ):
                raise HTTPException(422, "Invalid dashboard widget")
    elif data.kind == "recovery_request":
        if values.get("environment") != "non-production" or values.get(
            "status"
        ) not in ("requested", "approved", "rejected", "verified"):
            raise HTTPException(
                422,
                "Recovery requests require a non-production target and explicit state",
            )
        if len(str(values.get("procedure", ""))) < 20:
            raise HTTPException(422, "Provide the verified offline recovery procedure")
        if values.get("status") == "verified":
            raise HTTPException(
                422,
                "Verification is recorded by the recovery test, not a manual status",
            )
    elif data.kind == "support_access_request":
        if values.get("status") not in ("requested", "revoked"):
            raise HTTPException(
                422,
                "Support access cannot grant impersonation; use explicit managed memberships",
            )
        try:
            expiry = datetime.fromisoformat(values["expiresAt"])
        except (ValueError, KeyError, TypeError):
            raise HTTPException(422, "Support request requires an ISO expiry")
        seconds = (
            expiry.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
        ).total_seconds()
        if not 0 < seconds <= 8 * 3600:
            raise HTTPException(422, "Support requests expire within eight hours")


@router.get("/policies")
def policies(
    kind: str,
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    if kind not in {
        "branding",
        "dashboard",
        "governance",
        "error_resolution",
        "recovery_request",
        "support_access_request",
    }:
        raise HTTPException(422, "Unknown policy kind")
    rows = (
        db.query(ServicePolicy)
        .filter_by(organization_id=companyId, kind=kind)
        .order_by(ServicePolicy.id.desc())
        .limit(100)
        .all()
    )
    if kind == "dashboard":
        rows = [
            r
            for r in rows
            if r.scope_key.startswith(f"company:{companyId}:dashboard:user:{actor.id}:")
            or actor.role_id in (r.values_json or {}).get("sharedRoles", [])
        ]
    return [serialize(row) for row in rows]


@router.put("/policies")
def save_policy(
    data: PolicyInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(
        db,
        actor,
        data.companyId,
        request,
        data.kind in {"recovery_request", "support_access_request"},
    )
    validate_policy(data)
    if data.kind == "dashboard" and not data.key.startswith(f"user:{actor.id}:"):
        raise HTTPException(403, "Dashboard ownership must match the current user")
    if data.kind == "governance":
        data.key = f"{data.values['module']}:{data.values['entity']}"
    key = f"company:{data.companyId}:{data.kind}:{data.key}"
    row = (
        db.query(ServicePolicy)
        .filter_by(scope_key=key, kind=data.kind)
        .with_for_update()
        .first()
    )
    if row and row.version != data.version or not row and data.version:
        raise HTTPException(409, "Policy version changed")
    existed = row is not None
    if not row:
        row = ServicePolicy(
            scope_key=key, organization_id=data.companyId, kind=data.kind, version=0
        )
        db.add(row)
    if (
        data.kind == "recovery_request"
        and data.values.get("status") == "approved"
        and (
            not existed
            or (row.values_json or {}).get("status") != "requested"
            or row.updated_by == actor.id
        )
    ):
        raise HTTPException(
            403, "Recovery requires an independent approving administrator"
        )
    row.values_json, row.updated_by = data.values, actor.id
    row.version += 1
    audit(
        db,
        actor,
        data.companyId,
        "policy.saved",
        data.reason,
        request,
        {"kind": data.kind, "key": data.key, "version": row.version},
    )
    db.commit()
    return serialize(row)


@router.get("/branding")
def branding(
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    if not actor.is_superuser and companyId not in service.companies_for(db, actor):
        raise HTTPException(403, "Company membership required")
    row = (
        db.query(ServicePolicy)
        .filter_by(scope_key=f"company:{companyId}:branding:theme", kind="branding")
        .first()
    )
    return {
        "values": row.values_json if row else {},
        "domainStatus": "unverified",
        "tlsStatus": "unknown",
        "domainRouting": "not configured",
    }


class TicketInput(Command):
    subject: str = Field(min_length=3, max_length=300)
    description: str = Field(min_length=3, max_length=10000)
    module: str
    priority: Literal["Low", "Medium", "High", "Critical"] = "Medium"
    kind: Literal["support", "incident"] = "support"
    assignedTo: int | None = None
    relatedErrors: list[str] = Field(default_factory=list, max_length=50)


@router.get("/tickets")
def tickets(
    companyId: int = 1,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    query = db.query(HelpdeskTicket).filter(HelpdeskTicket.organization_id == companyId)
    return {
        "items": [
            serialize(row)
            for row in query.order_by(HelpdeskTicket.id.desc())
            .offset((page - 1) * 50)
            .limit(50)
        ],
        "total": query.count(),
        "page": page,
    }


@router.post("/tickets", status_code=201)
def create_ticket(
    data: TicketInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    if data.module not in {m["key"] for m in catalog(db)}:
        raise HTTPException(422, "Unknown module")
    if data.assignedTo and (
        not db.get(User, data.assignedTo)
        or data.companyId
        not in service.companies_for(db, db.get(User, data.assignedTo))
    ):
        raise HTTPException(422, "Assignee must belong to the company")
    row = HelpdeskTicket(
        organization_id=data.companyId,
        module_key=data.module,
        ticket_number="MS-" + uuid.uuid4().hex[:20],
        subject=data.subject,
        description=data.description,
        priority=data.priority,
        status="Open",
        assigned_to=data.assignedTo,
        detail_json={
            "kind": data.kind,
            "relatedErrors": data.relatedErrors,
            "createdBy": actor.id,
        },
    )
    db.add(row)
    db.flush()
    audit(
        db,
        actor,
        data.companyId,
        "ticket.created",
        data.reason,
        request,
        {"ticketId": row.id},
    )
    db.commit()
    return serialize(row)


class TicketChange(Command):
    status: Literal["Open", "In Progress", "Pending", "Resolved", "Closed"]
    assignedTo: int | None = None
    comment: str = Field(min_length=3, max_length=10000)


@router.put("/tickets/{ticket_id}")
def update_ticket(
    ticket_id: int,
    data: TicketChange,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    row = (
        db.query(HelpdeskTicket)
        .filter_by(id=ticket_id, organization_id=data.companyId)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(404, "Ticket not found")
    if row.version != data.version:
        raise HTTPException(409, "Ticket version changed")
    if data.assignedTo and (
        not db.get(User, data.assignedTo)
        or data.companyId
        not in service.companies_for(db, db.get(User, data.assignedTo))
    ):
        raise HTTPException(422, "Assignee must belong to the company")
    row.status, row.assigned_to = data.status, data.assignedTo
    row.version += 1
    if data.status == "Closed":
        row.closed_at = datetime.now(timezone.utc)
    if data.status == "Resolved":
        row.resolved_at = datetime.now(timezone.utc)
    db.add(
        HelpdeskReply(
            ticket_id=row.id, user_id=actor.id, message=data.comment, is_internal=True
        )
    )
    audit(
        db,
        actor,
        data.companyId,
        "ticket.updated",
        data.reason,
        request,
        {"ticketId": row.id, "status": row.status},
    )
    db.commit()
    return serialize(row)


@router.get("/tickets/{ticket_id}/comments")
def comments(
    ticket_id: int,
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    if (
        not db.query(HelpdeskTicket.id)
        .filter_by(id=ticket_id, organization_id=companyId)
        .first()
    ):
        raise HTTPException(404, "Ticket not found")
    return [
        serialize(row)
        for row in db.query(HelpdeskReply)
        .filter_by(ticket_id=ticket_id)
        .order_by(HelpdeskReply.id)
        .limit(200)
    ]


@router.get("/diagnostics")
def diagnostics(
    request: Request,
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    result = {
        "schemaHeads": (
            [
                row[0]
                for row in db.connection().exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                )
            ]
            if inspect(db.connection()).has_table("alembic_version")
            else []
        ),
        "modules": [
            {"key": m["key"], "installed": m["installed"]} for m in catalog(db)
        ],
        "health": health(db, actor, companyId),
        "errorKeys": [row["key"] for row in errors(db, actor, companyId)["items"]],
    }
    audit(
        db,
        actor,
        companyId,
        "diagnostics.export",
        "Export sanitized diagnostics",
        request,
    )
    db.commit()
    return Response(
        json.dumps(result, default=str),
        media_type="application/json",
        headers={
            "Content-Disposition": "attachment; filename=diagnostics.json",
            "Cache-Control": "no-store",
        },
    )


@router.get("/backups")
def backups(db: Session = Depends(get_db), actor: User = Depends(admin)):
    if not actor.is_superuser:
        raise HTTPException(
            403, "Global administrator required for all-company backups"
        )
    from app.services.data_backups import list_archives

    result = list_archives(actor)
    verified = {
        r.scope_key.rsplit(":", 1)[-1]: r.values_json
        for r in db.query(ServicePolicy).filter_by(kind="backup_verification")
    }
    for archive in result["archives"]:
        archive["verification"] = verified.get(archive["id"])
    return result


@router.post("/backups", status_code=201)
def backup(
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request, True)
    from app.services.data_backups import manual_archive

    result = manual_archive(actor)
    audit(
        db,
        actor,
        data.companyId,
        "backup.created",
        data.reason,
        request,
        {"backupId": result.get("id")},
    )
    db.commit()
    return result


@router.get("/actions")
def actions(
    companyId: int = 1, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company_access(db, actor, companyId)
    from app.apps.automation.models import AutomationScheduledJob

    items = [
        {
            "id": f"job:{row.id}",
            "type": "workflow",
            "priority": "high",
            "title": f"Execution #{row.id}: {row.status}",
            "path": "/admin/control/services/executions",
        }
        for row in db.query(AutomationScheduledJob)
        .filter(
            AutomationScheduledJob.organization_id == companyId,
            AutomationScheduledJob.status.in_(
                ["dead_letter", "reconciliation_required"]
            ),
        )
        .order_by(AutomationScheduledJob.id.desc())
        .limit(50)
    ]
    items += [
        {
            "id": "error:" + row["key"],
            "type": "error",
            "priority": row["severity"],
            "title": f"{row['type'] or 'HTTP 500'} · {row['frequency']} occurrences",
            "path": "/admin/control/enterprise/errors",
        }
        for row in errors(db, actor, companyId)["items"]
        if row["status"] != "resolved"
    ]
    items += [
        {
            "id": f"ticket:{row.id}",
            "type": "support",
            "priority": row.priority.lower(),
            "title": row.subject,
            "path": "/admin/control/enterprise/support",
        }
        for row in db.query(HelpdeskTicket)
        .filter(
            HelpdeskTicket.organization_id == companyId,
            HelpdeskTicket.status.notin_(["Closed", "Resolved"]),
        )
        .limit(50)
    ]
    return {
        "items": items,
        "approvalInbox": "/hrms/approvals",
        "security": "/admin/control/security",
    }


@router.post("/alerts/evaluate")
def operational_alerts(
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    from app.enterprise.operations import evaluate_alerts

    result = evaluate_alerts(db, data.companyId, actor.id)
    audit(db, actor, data.companyId, "alerts.evaluated", data.reason, request, result)
    db.commit()
    return result


@router.post("/backups/{backup_id}/verify")
def verify_backup(
    backup_id: str,
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request, True)
    if not re.fullmatch(r"[a-f0-9]{32}", backup_id):
        raise HTTPException(404, "Backup not found")
    from app.services.data_backups import backup_root, verify_archive, extract_archive
    import tempfile, sqlite3

    path = backup_root() / (backup_id + ".zip")
    if not path.is_file():
        raise HTTPException(404, "Backup not found")
    try:
        manifest = verify_archive(path)
        report = {
            "backupId": backup_id,
            "checksums": "verified",
            "files": manifest["file_count"],
            "databaseRestore": "not tested",
        }
        if manifest["database"] == "sqlite":
            with tempfile.TemporaryDirectory(prefix="suite-recovery-test-") as temp:
                from pathlib import Path

                directory = extract_archive(path, Path(temp) / "offline")
                with sqlite3.connect(
                    "file:" + str(directory / "database.sqlite3") + "?mode=ro", uri=True
                ) as connection:
                    if (
                        connection.execute("PRAGMA integrity_check").fetchone()[0]
                        != "ok"
                    ):
                        raise ValueError("Integrity check failed")
                report["databaseRestore"] = (
                    "verified in isolated temporary SQLite directory"
                )
    except (ValueError, OSError, KeyError):
        raise HTTPException(
            409, "Archive verification failed; inspect operational logs"
        ) from None
    key = f"company:{data.companyId}:backup_verification:{backup_id}"
    row = (
        db.query(ServicePolicy)
        .filter_by(scope_key=key, kind="backup_verification")
        .first()
    )
    existed = row is not None
    if not row:
        row = ServicePolicy(
            scope_key=key,
            kind="backup_verification",
            organization_id=data.companyId,
            version=0,
            updated_by=actor.id,
        )
        db.add(row)
    row.values_json = report
    row.version += 1
    row.updated_by = actor.id
    audit(db, actor, data.companyId, "backup.verified", data.reason, request, report)
    db.commit()
    return report


@router.post("/flags/{flag_id}/rollback")
def rollback_flag(
    flag_id: int,
    data: Command,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request)
    row = (
        db.query(BOSFeatureFlag)
        .filter_by(id=flag_id, company_id=data.companyId)
        .with_for_update()
        .first()
    )
    if not row:
        raise HTTPException(404, "Flag not found")
    current = copy.deepcopy(row.value_json or {})
    if current.get("version", 0) != data.version:
        raise HTTPException(409, "Flag version changed")
    previous = current.get("previous")
    if not previous or not previous.get("config"):
        raise HTTPException(409, "No previous configured version")
    config = copy.deepcopy(previous["config"])
    config["version"] = data.version + 1
    config["previous"] = {
        "enabled": row.enabled,
        "config": {k: v for k, v in current.items() if k != "previous"},
    }
    row.enabled = previous["enabled"]
    row.value_json = config
    audit(
        db,
        actor,
        data.companyId,
        "flag.rollback",
        data.reason,
        request,
        {"flagId": flag_id, "version": config["version"]},
    )
    db.commit()
    return serialize(row)


@router.get("/relationships")
def relationships(
    module: str,
    entity: str,
    recordId: int = Query(gt=0),
    companyId: int = 1,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    company_access(db, actor, companyId)
    from app.shared.gateway import read_record

    read_record(db, actor, companyId, module, entity, recordId)
    rows = (
        db.query(BOSEntityLink)
        .filter_by(
            company_id=companyId,
            source_module=module,
            source_entity=entity,
            source_entity_id=str(recordId),
            active=True,
        )
        .order_by(BOSEntityLink.id)
        .limit(100)
    )
    result = []
    for row in rows:
        if (row.target_module, row.target_entity) not in RECORDS or not str(
            row.target_entity_id
        ).isdigit():
            continue
        try:
            read_record(
                db,
                actor,
                companyId,
                row.target_module,
                row.target_entity,
                int(row.target_entity_id),
            )
        except HTTPException as exc:
            if exc.status_code in {403, 404}:
                continue
            raise
        result.append(
            {
                "linkId": row.id,
                "type": row.link_type,
                "module": row.target_module,
                "entity": row.target_entity,
                "recordId": int(row.target_entity_id),
            }
        )
    return {
        "source": {"module": module, "entity": entity, "recordId": recordId},
        "relationships": result,
        "evidence": "persisted Business OS entity links; each endpoint authorized",
    }


@router.get("/tickets/{ticket_id}")
def get_ticket(
    ticket_id: int, db: Session = Depends(get_db), actor: User = Depends(admin)
):
    company = getattr(actor, "organization_id", None) or service.primary_company(actor)
    company_access(db, actor, company)
    row = (
        db.query(HelpdeskTicket)
        .filter_by(id=ticket_id, organization_id=company)
        .first()
    )
    if not row:
        raise HTTPException(404, "Ticket not found")
    return serialize(row)


from app.shared.contracts import register_record, RecordContract

register_record(
    RecordContract(
        "hrms", "support_ticket", "/access/enterprise/tickets/{id}", "helpdesk_view"
    )
)
register_record(RecordContract("hrms", "employee", "/employees/{id}", "employee_view"))


class BackupPolicyInput(Command):
    enabled: bool = False
    intervalHours: int = Field(default=24, ge=1, le=720)
    retainAutomatic: int = Field(default=14, ge=2, le=90)


@router.put("/backups/policy")
def backup_policy(
    data: BackupPolicyInput,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin),
):
    change(db, actor, data.companyId, request, True)
    from app.services.data_backups import FullPolicy, full_policy

    result = full_policy(
        FullPolicy(
            enabled=data.enabled,
            interval_hours=data.intervalHours,
            retain_automatic=data.retainAutomatic,
        ),
        actor,
    )
    audit(
        db,
        actor,
        data.companyId,
        "backup.policy",
        data.reason,
        request,
        {
            "enabled": data.enabled,
            "intervalHours": data.intervalHours,
            "retainAutomatic": data.retainAutomatic,
        },
    )
    db.commit()
    return result
