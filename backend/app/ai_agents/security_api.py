"""Human-only administration of mandatory AI controls and tighter limits."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from pydantic import Field
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user
from app.access.api import admin, company_access, Strict, serialize
from app.access.control import mutate, record
from app.access import service
from app.ai_agents.security import (
    VERSION,
    PERMANENT,
    limits,
    company,
    _authorize_tool,
    metadata,
)
from app.ai_agents.security_catalog import LEGACY, SUITE, ASSISTANT, ACTIONS
from app.ai_agents.models import AiAuditLog
from app.shared.models import ServicePolicy
from app.models.user import User

router = APIRouter(prefix="/access/ai-security", tags=["Mandatory AI Security"])


def tool_catalog():
    from app.ai_agents.tools.definitions import ALL_TOOL_DEFINITIONS
    from app.ai_operator.suite_tools import TOOLS

    rows = []
    for t in ALL_TOOL_DEFINITIONS:
        rows.append(
            {
                "id": "legacy:" + t.tool_name,
                "module": t.module,
                "permission": t.required_permission,
                "risk": t.risk_level,
                "confirmation": t.requires_approval,
                "approved": LEGACY.get(t.tool_name)
                == (t.module, t.executor, t.required_permission, t.requires_approval),
                "schema": t.input_schema,
                "handler": t.executor,
                "version": 1,
            }
        )
    for name, t in TOOLS.items():
        rows.append(
            {
                "id": "suite:" + name,
                "module": t.module,
                "permission": list(t.permissions),
                "risk": "restricted" if t.method != "GET" else "read",
                "confirmation": t.method != "GET",
                "approved": SUITE.get(name)
                == (t.module, t.method, t.path, t.permissions),
                "schema": {"fields": list(t.fields)},
                "handler": t.method + " " + t.path,
                "version": 1,
            }
        )
    from app.ai_operator.assistant_tools import registry

    for t in registry():
        rows.append(
            {
                "id": "assistant:" + t["name"],
                "module": "cross-module",
                "permission": t["permissions"],
                "risk": "restricted" if t["confirmation_required"] else "read",
                "confirmation": t["confirmation_required"],
                "approved": t["name"] in ASSISTANT,
                "schema": t["input_schema"],
                "handler": "fixed business service adapter",
                "version": 1,
            }
        )
    return rows


@router.get("/context")
def current_context(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    tenant = company(user)
    policy = service.policy_for(db, user, tenant)
    grants = (
        service.resolved_grants(db, policy)
        if policy
        else service.legacy_grants(db, user, tenant)
    )
    from app.access.entitlements import apply

    grants = apply(db, tenant, grants)
    return {
        "user": {"id": user.id, "email": user.email},
        "companyId": tenant,
        "policyVersion": VERSION,
        "modules": [key for key, g in grants.items() if g.get("enabled")],
        "mode": "permission-bound; write actions require exact confirmation",
        "limits": limits(db, tenant),
        "baselineCannotBeDisabled": True,
    }


@router.get("")
def policy(
    companyId: int = 1, db: Session = Depends(get_db), user: User = Depends(admin)
):
    company_access(db, user, companyId)
    row = (
        db.query(ServicePolicy)
        .filter_by(scope_key=f"company:{companyId}:ai_security", kind="ai_security")
        .first()
    )
    return {
        "policyVersion": VERSION,
        "version": row.version if row else 0,
        "lastConfigurationReview": row.updated_at if row else None,
        "limits": limits(db, companyId),
        "permanentlyProhibited": PERMANENT,
        "tools": tool_catalog(),
        "mandatory": {
            "sessionBinding": True,
            "tenantBinding": True,
            "nativePermissions": True,
            "singleUseConfirmation": True,
            "permissionRevocation": True,
            "destructiveOperations": "permanently denied",
            "arbitrarySqlShellFilesystem": "not exposed",
            "audit": "append-only metadata; no raw prompts or arguments",
        },
        "unverified": [
            "Live model/provider behavior is not a security authorization control",
            "Independently deployed inventory application needs its own adapter",
        ],
    }


class LimitsInput(Strict):
    companyId: int = Field(gt=0)
    version: int = Field(ge=0)
    max_calls: int = Field(ge=1, le=12)
    max_seconds: int = Field(ge=5, le=120)
    max_result_bytes: int = Field(ge=1000, le=32000)
    disabled_tools: list[str] = Field(default_factory=list, max_length=150)
    reason: str = Field(min_length=3, max_length=500)


@router.put("")
def configure(
    data: LimitsInput,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    company_access(db, user, data.companyId)
    from app.access.catalog import permission_names

    if not user.is_superuser and "settings_manage" not in permission_names(user):
        raise HTTPException(403, "AI security configuration permission required")
    mutate(request, user)
    from app.models.company import Company

    db.query(Company).filter_by(id=data.companyId).with_for_update().one()
    allowed = {row["id"] for row in tool_catalog()}
    if set(data.disabled_tools) - allowed:
        raise HTTPException(422, "Unknown tool cannot be enabled or configured")
    row = (
        db.query(ServicePolicy)
        .filter_by(
            scope_key=f"company:{data.companyId}:ai_security", kind="ai_security"
        )
        .with_for_update()
        .first()
    )
    if row and row.version != data.version or not row and data.version:
        raise HTTPException(409, "AI policy changed; reload")
    if not row:
        row = ServicePolicy(
            scope_key=f"company:{data.companyId}:ai_security",
            organization_id=data.companyId,
            kind="ai_security",
            version=0,
        )
        db.add(row)
    row.values_json = data.model_dump(
        include={"max_calls", "max_seconds", "max_result_bytes", "disabled_tools"}
    )
    row.version += 1
    row.updated_by = user.id
    record(
        db,
        user,
        data.companyId,
        "ai.security.configured",
        {"reason": data.reason, "version": row.version, "policy": VERSION},
        request,
    )
    db.commit()
    return {
        "version": row.version,
        "policyVersion": VERSION,
        "mandatoryBaselineEnabled": True,
    }


@router.get("/logs")
def logs(
    companyId: int = 1,
    page: int = Query(1, ge=1),
    blocked: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(admin),
):
    company_access(db, user, companyId)
    query = db.query(AiAuditLog).filter(AiAuditLog.organization_id == companyId)
    if blocked:
        query = query.filter(AiAuditLog.status.in_(["failed", "warning"]))
    return {
        "items": [
            {
                **serialize(row),
                "input_json": metadata(row.input_json),
                "output_json": metadata(row.output_json),
            }
            for row in query.order_by(AiAuditLog.id.desc())
            .offset((page - 1) * 50)
            .limit(50)
        ],
        "page": page,
        "pageSize": 50,
        "total": query.count(),
    }
