"""Mandatory AI execution policy. Model output never supplies authority."""

import copy, hashlib, hmac, json, re, time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import event, select, func
from sqlalchemy.orm import Session, object_session
from app.core.config import settings
from app.ai_agents.security_catalog import LEGACY, SUITE, ASSISTANT

VERSION = "ai-zero-trust-1"
MODULES = {
    "PMS": "project_management",
    "CRM": "crm",
    "HRMS": "hrms",
    "SRM": "srm",
    "FAM": "fam",
    "CROSS": "ai",
}
PERMANENT = (
    "workspace reset/deletion",
    "company/organization deletion",
    "permanent or bulk record deletion",
    "SQL/schema/migration execution",
    "shell/filesystem/infrastructure changes",
    "role/permission/security changes",
    "audit/backup/storage deletion",
    "AI self-approval or standing administrative consent",
)
IDENTITY_KEYS = {
    "userid",
    "actinguserid",
    "organizationid",
    "tenantid",
    "tenantoverride",
    "isadmin",
    "issuperuser",
    "role",
    "unrestricted",
    "bypasspermissions",
    "systemmode",
    "developermode",
    "force",
    "authorization",
    "accesstoken",
    "rawsql",
    "sql",
    "shell",
    "executor",
    "securitycontext",
}
ORIGIN = ContextVar("suite_ai_origin", default=None)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def company(user):
    from app.access.service import primary_company

    return getattr(user, "organization_id", None) or primary_company(user)


def limits(db, tenant):
    from app.shared.models import ServicePolicy

    row = (
        db.query(ServicePolicy)
        .filter_by(scope_key=f"company:{tenant}:ai_security", kind="ai_security")
        .first()
    )
    data = (row.values_json or {}) if row else {}
    return {
        "max_calls": min(12, data.get("max_calls", 8)),
        "max_seconds": min(120, data.get("max_seconds", 60)),
        "max_result_bytes": min(32000, data.get("max_result_bytes", 16000)),
        "disabled_tools": data.get("disabled_tools", []),
        "version": row.version if row else 0,
    }


def fingerprint(db, user, tenant):
    from app.models.user import User, Permission, role_permissions
    from app.access import service, entitlements

    table = User.__table__
    identity = (
        db.connection()
        .execute(
            select(
                table.c.id, table.c.role_id, table.c.is_superuser, table.c.is_active
            ).where(table.c.id == user.id)
        )
        .mappings()
        .first()
    )
    if not identity or not identity["is_active"]:
        raise HTTPException(403, "Active AI actor required")
    if (
        identity["is_superuser"] != bool(user.is_superuser)
        or identity["role_id"] != user.role_id
    ):
        raise HTTPException(403, "AI actor identity changed")
    if not user.is_superuser and tenant not in service.companies_for(db, user):
        raise HTTPException(403, "AI company membership required")
    policy = service.policy_for(db, user, tenant)
    if policy and policy.status != "active":
        raise HTTPException(403, "AI access revoked")
    names = (
        db.connection()
        .execute(
            select(Permission.__table__.c.name)
            .join(
                role_permissions,
                role_permissions.c.permission_id == Permission.__table__.c.id,
            )
            .where(role_permissions.c.role_id == identity["role_id"])
        )
        .scalars()
        .all()
    )
    from app.ai_agents.models import (
        AiAgentPermission,
        AiAgentSetting,
        AiSecuritySetting,
    )
    from sqlalchemy import or_

    agent_state = {}
    for model in (AiAgentPermission, AiAgentSetting, AiSecuritySetting):
        table = model.__table__
        rows = (
            db.connection()
            .execute(
                select(table).where(
                    or_(table.c.company_id == tenant, table.c.company_id.is_(None))
                )
            )
            .mappings()
        )
        visible = []
        for row in rows:
            if model is AiSecuritySetting:
                flags = {
                    key: bool(row[key])
                    for key in (
                        "ai_enabled",
                        "crm_ai_enabled",
                        "pms_ai_enabled",
                        "hrms_ai_enabled",
                        "cross_ai_enabled",
                    )
                }
                if all(flags.values()):
                    continue
                visible.append({"company_id": row["company_id"], **flags})
            elif model is AiAgentSetting:
                if (
                    row["is_enabled"]
                    and not row["auto_action_enabled"]
                    and row["approval_required"]
                    and row["data_access_scope"] in (None, "own_records")
                ):
                    continue
                visible.append(
                    {
                        key: row[key]
                        for key in (
                            "company_id",
                            "agent_id",
                            "is_enabled",
                            "auto_action_enabled",
                            "approval_required",
                            "data_access_scope",
                        )
                    }
                )
            elif row["user_id"] in (None, user.id) and row["role_id"] in (
                None,
                identity["role_id"],
            ):
                visible.append(
                    {
                        key: row[key]
                        for key in (
                            "company_id",
                            "agent_id",
                            "user_id",
                            "role_id",
                            "can_use",
                            "can_configure",
                            "can_approve_actions",
                            "can_view_logs",
                            "can_export_conversations",
                        )
                    }
                )
        agent_state[model.__tablename__] = sorted(
            visible, key=lambda value: json.dumps(value, sort_keys=True, default=str)
        )
    from app.shared.models import ServicePolicy

    epoch = (
        db.connection()
        .execute(
            select(ServicePolicy.__table__.c.version).where(
                ServicePolicy.__table__.c.scope_key == f"company:{tenant}:ai_acl_epoch",
                ServicePolicy.__table__.c.kind == "ai_acl_epoch",
            )
        )
        .scalar()
        or 0
    )
    return digest(
        {
            "aclEpoch": epoch,
            "agent_state": agent_state,
            "actor": dict(identity),
            "company": tenant,
            "policyVersion": policy.version if policy else None,
            "grants": (
                service.resolved_grants(db, policy)
                if policy
                else service.legacy_grants(db, user, tenant)
            ),
            "nativePermissions": sorted(names),
            "entitlements": entitlements.states(db, tenant),
            "aiPolicy": limits(db, tenant)["version"],
        }
    )


def session_check(db, user, session_id):
    if session_id is None:
        return  # Only signed, code-owned internal delegations use this path.
    from app.models.user import UserSession

    row = (
        db.connection()
        .execute(
            UserSession.__table__.select().where(
                UserSession.__table__.c.id == int(session_id)
            )
        )
        .mappings()
        .first()
    )
    if (
        not row
        or row["user_id"] != user.id
        or row["status"] != "Active"
        or row["expires_at"]
        and utc(row["expires_at"]) <= datetime.now(timezone.utc)
    ):
        raise HTTPException(401, "AI initiator session is no longer active")


def utc(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def signature(data):
    return hmac.new(
        settings.SECRET_KEY.encode(), digest(data).encode(), hashlib.sha256
    ).hexdigest()


def seal(db, user, payload=None, session_id=None, tenant=None):
    request = db.info.get("ai_request_context")
    tenant = tenant or company(user)
    if request and request["user_id"] == user.id:
        session_id = request["session_id"]
        if session_id is None:
            raise HTTPException(401, "Sign in again to establish an AI session")
    session_id = (
        session_id
        if session_id is not None
        else getattr(user, "_suite_session_id", None)
    )
    session_check(db, user, session_id)
    data = {
        "user_id": user.id,
        "company_id": tenant,
        "session_id": session_id,
        "fingerprint": fingerprint(db, user, tenant),
        "policy": VERSION,
        "nonce": uuid4().hex,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "operation": digest(payload) if payload is not None else None,
    }
    return {**data, "signature": signature(data)}


def verify(db, user, context, payload=None, confirmation=False, history=False):
    if not isinstance(context, dict):
        raise HTTPException(
            409, "Prepare a fresh AI preview; legacy context is unverified"
        )
    data = {k: v for k, v in context.items() if k != "signature"}
    if not hmac.compare_digest(str(context.get("signature", "")), signature(data)):
        raise HTTPException(409, "AI security context was modified")
    if (
        data.get("policy") != VERSION
        or data.get("user_id") != user.id
        or data.get("company_id") != company(user)
    ):
        raise HTTPException(403, "AI actor or company context does not match")
    if not history:
        session_check(db, user, data.get("session_id"))
    request = db.info.get("ai_request_context")
    if confirmation and request and data.get("session_id") != request["session_id"]:
        raise HTTPException(403, "Confirm using the original authenticated session")
    if data.get("fingerprint") != fingerprint(db, user, company(user)):
        raise HTTPException(
            403, "AI permissions changed; start a fresh conversation or preview"
        )
    if payload is not None and data.get("operation") != digest(payload):
        raise HTTPException(409, "The exact approved AI operation changed")
    if confirmation and datetime.now(timezone.utc) - utc(data["issued_at"]) > timedelta(
        minutes=15
    ):
        raise HTTPException(409, "AI confirmation expired; prepare a fresh preview")
    return data


def strict_input(schema, value, depth=0):
    if depth > 10:
        raise HTTPException(422, "AI input nesting limit exceeded")
    if not isinstance(value, dict):
        raise HTTPException(422, "AI tool arguments must be an object")
    properties = schema.get("properties", {})
    if set(value) - set(properties):
        raise HTTPException(422, "Unknown AI tool arguments")
    for key in schema.get("required", []):
        if key not in value or value[key] is None or value[key] == "":
            raise HTTPException(422, "Missing required AI tool argument")

    def walk(item, level=0):
        if level > 10:
            raise HTTPException(422, "AI input nesting limit exceeded")
        if isinstance(item, dict):
            for key, child in item.items():
                if re.sub("[^a-z0-9]", "", str(key).lower()) in IDENTITY_KEYS or str(
                    key
                ).startswith("_"):
                    raise HTTPException(
                        422, "AI authority or internal fields are prohibited"
                    )
                walk(child, level + 1)
        elif isinstance(item, list):
            if len(item) > 100:
                raise HTTPException(422, "AI collection limit exceeded")
            for child in item:
                walk(child, level + 1)
        elif isinstance(item, str) and len(item) > 8000:
            raise HTTPException(422, "AI text limit exceeded")

    walk(value)
    try:
        encoded = json.dumps(value, default=str, allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError):
        raise HTTPException(422, "AI arguments are not bounded JSON") from None
    if len(encoded) > 16000:
        raise HTTPException(422, "AI input limit exceeded")
    for key, item in value.items():
        field = properties[key]
        kind = field.get("type")
        if item is None:
            continue
        valid = {
            "integer": type(item) is int,
            "number": type(item) in (int, float),
            "string": isinstance(item, str),
            "boolean": type(item) is bool,
            "array": isinstance(item, list),
            "object": isinstance(item, dict),
        }
        if isinstance(kind, str) and kind in valid and not valid[kind]:
            raise HTTPException(422, "AI argument type mismatch")
        if field.get("enum") and item not in field["enum"]:
            raise HTTPException(422, "AI argument value is not allowed")


def _authorize_tool(db, user, engine, name, definition=None):
    from app.shared.contracts import authorize

    tenant = company(user)
    if engine == "legacy":
        approved = LEGACY.get(name)
        if (
            not approved
            or not definition
            or (
                definition.module,
                definition.executor,
                definition.required_permission,
                definition.requires_approval,
            )
            != approved
        ):
            raise HTTPException(403, "AI tool is not code-approved")
        module, _, permission, write = approved
    elif engine == "suite":
        approved = SUITE.get(name)
        if (
            not approved
            or not definition
            or (
                definition.module,
                definition.method,
                definition.path,
                definition.permissions,
            )
            != approved
        ):
            raise HTTPException(403, "AI tool is not code-approved")
        module, method, _, _ = approved
        permission = None
        write = method != "GET"
    elif engine == "assistant":
        if name not in ASSISTANT:
            raise HTTPException(403, "AI tool is not code-approved")
        from app.ai_operator.assistant_tools import MUTATIONS

        module = (
            "SRM"
            if name.startswith(("invoices.", "payments.", "reports."))
            else "CRM" if name == "customers.search" else "PMS"
        )
        permission = None
        write = name in MUTATIONS
    else:
        raise HTTPException(403, "Unknown AI execution engine")
    if f"{engine}:{name}" in limits(db, tenant)["disabled_tools"]:
        raise HTTPException(403, "AI tool disabled by security policy")
    authorize(db, user, tenant, "ai", "view")
    from app.access import service
    from app.access.catalog import permission_names

    policy = service.policy_for(db, user, tenant)
    names = (
        set(
            service.resolved_grants(db, policy)
            .get(MODULES[module], {})
            .get("permissions", [])
        )
        if policy and not user.is_superuser
        else permission_names(user)
    )
    alternatives = {
        "crm_manage": {"crm_manage", "crm_admin"},
        "crm_view": {"crm_view", "crm_manage", "crm_admin"},
        "pms_view": {
            "pms_view",
            "pms_manage_tasks",
            "pms_manage_projects",
            "pms_admin",
        },
        "pms_manage_tasks": {"pms_manage_tasks", "pms_manage_projects", "pms_admin"},
        "employee_view": {
            "employee_view",
            "employee_update",
            "employee_sensitive_view",
        },
    }
    if (
        permission
        and not user.is_superuser
        and not names.intersection(alternatives.get(permission, {permission}))
    ):
        raise HTTPException(403, "Native AI tool permission required")
    if (
        engine == "suite"
        and definition.permissions
        and not user.is_superuser
        and not names.intersection(definition.permissions)
    ):
        raise HTTPException(403, "Native AI action permission required")
    authorize(
        db, user, tenant, MODULES[module], "create" if write and policy else "view"
    )
    return MODULES[module]


def authorize_tool(db, user, engine, name, definition=None):
    from app.ai_agents.services.audit import AiAuditService

    known = name in LEGACY or name in SUITE or name in ASSISTANT
    label = name if known else "unregistered:" + digest(str(name))[:12]
    try:
        module = _authorize_tool(db, user, engine, name, definition)
    except HTTPException:
        AiAuditService(db).log(
            user=user,
            agent_id=None,
            module=getattr(definition, "module", "CROSS"),
            action="AI_POLICY_DENIED",
            input_json={"tool_name": label, "policy": VERSION},
            output_json={"authorization": "denied", "blocked": True},
            status="failed",
        )
        raise
    AiAuditService(db).log(
        user=user,
        agent_id=None,
        module=getattr(definition, "module", "CROSS"),
        action="AI_POLICY_ALLOWED",
        input_json={"tool_name": label, "policy": VERSION},
        output_json={"authorization": "allowed"},
        status="success",
    )
    return module


@contextmanager
def scoped(db, user, module):
    from app.enterprise.analytics import scoped as existing_scope

    # Reuse the existing record adapter, including company filters for Super Admin.
    # Legacy actors get their actual legacy grants, never an agent-configured wider scope.
    from app.access import service
    from app.access.scope import install_scope

    saved = {
        k: v
        for k, v in user.__dict__.items()
        if k.startswith("_suite_") or k == "organization_id"
    }
    policy = service.policy_for(db, user, company(user))
    grants = (
        service.resolved_grants(db, policy)
        if policy and not user.is_superuser
        else service.legacy_grants(db, user, company(user))
    )
    user.organization_id = company(user)
    user._suite_current_module = module
    cleanup = install_scope(db, user, company(user), grants)
    try:
        yield
    finally:
        cleanup()
        for key in list(user.__dict__):
            if key.startswith("_suite_") or key == "organization_id":
                user.__dict__.pop(key, None)
        user.__dict__.update(saved)


def plan_step(step):
    if step.tool not in {
        "update_task",
        "add_checklist",
        "move_to_sprint",
        "schedule_task",
        "add_dependency",
        "update_checklist",
        "add_comment",
    }:
        raise HTTPException(
            403,
            "AI cannot permanently remove records, checklists or dependencies; use the authorized human interface",
        )


def boundary(method, path):
    if method == "DELETE":
        raise HTTPException(403, "AI permanent deletion is prohibited")
    blocked = {
        "reset",
        "purge",
        "truncate",
        "drop",
        "restore",
        "permissions",
        "roles",
        "security",
        "backups",
        "providers",
        "settings",
        "internal",
        "execute-sql",
        "shell",
    }
    if set(path.lower().split("/")) & blocked:
        raise HTTPException(
            403, "Administrative and destructive AI endpoints are prohibited"
        )
    # Exact capability paths are checked by callers; this is an independent baseline.


def redact(value, depth=0):
    if depth > 8:
        return "[bounded]"
    if isinstance(value, dict):
        return {
            str(k): redact(v, depth + 1)
            for k, v in value.items()
            if not any(
                word in str(k).lower()
                for word in (
                    "password",
                    "secret",
                    "token",
                    "credential",
                    "encrypted_key",
                    "api_key",
                    "apikey",
                    "private_key",
                    "database_url",
                    "salary",
                    "ctc",
                    "bank_account",
                    "aadhaar",
                    "pan_number",
                )
            )
        }
    if isinstance(value, list):
        return [redact(v, depth + 1) for v in value[:50]]
    if isinstance(value, str):
        return value[:8000]
    return value


def bounded_result(db, user, value):
    """Cap disclosed tool data in bytes; preserve valid JSON on truncation."""
    value = redact(value)
    cap = limits(db, company(user))["max_result_bytes"]
    if len(json.dumps(value, default=str, ensure_ascii=False).encode()) > cap:
        return {
            "truncated": True,
            "message": "Result exceeds the AI disclosure limit; narrow the query.",
        }
    return value


def metadata(value):
    allowed = {
        "tool_name",
        "approval_id",
        "run_id",
        "suite_run_id",
        "conversation_id",
        "message_id",
        "project_id",
        "task_id",
        "plan_hash",
        "error_code",
        "status",
        "module",
        "policy",
        "authorization",
        "required_permission",
        "approval_status",
        "correlation_id",
        "risk_level",
        "success",
        "count",
        "sanitized",
        "blocked",
    }
    if not isinstance(value, dict):
        return {}
    result = {
        k: v
        for k, v in value.items()
        if k in allowed and isinstance(v, (str, int, float, bool, type(None)))
    }
    known = set(LEGACY) | set(SUITE) | set(ASSISTANT)
    name = result.get("tool_name")
    if name and name not in known:
        result["tool_name"] = "unknown:" + digest(name)[:16]
    return result


def operation(row):
    if row.__class__.__name__ == "AiActionApproval":
        return row.proposed_action_json
    if row.__class__.__name__ == "AssistantMessage":
        return {
            "tool": row.tool,
            "arguments": row.arguments,
            "proposal": row.proposal,
            "approval_hash": row.approval_hash,
        }
    return None


@event.listens_for(Session, "before_flush")
def bind_records(db, flush_context, instances):
    from app.models.user import User

    names = {
        "AiConversation",
        "AiHandoffNote",
        "AiActionApproval",
        "OperatorRun",
        "OperatorProposal",
        "SuiteRun",
        "AssistantConversation",
        "AssistantMessage",
        "AssistantArtifact",
    }
    with db.no_autoflush:
        for row in list(db.new):
            if row.__class__.__name__ not in names or row.security_context:
                continue
            user_id = getattr(row, "user_id", None) or getattr(row, "created_by", None)
            parent = None
            if row.__class__.__name__ == "AssistantMessage":
                from app.ai_operator.assistant_models import AssistantConversation

                parent = db.get(AssistantConversation, row.conversation_id)
                user_id = parent.user_id if parent else None
            if not user_id:
                continue
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(403, "AI initiator missing")
            inherited = None
            if row.__class__.__name__ == "AiActionApproval":
                values = (row.proposed_action_json or {}).get("input", {})
                from app.ai_operator.models import OperatorRun, OperatorProposal
                from app.ai_operator.suite_models import SuiteRun

                for field, model in (
                    ("run_id", OperatorRun),
                    ("proposal_id", OperatorProposal),
                    ("suite_run_id", SuiteRun),
                ):
                    if values.get(field):
                        source = db.get(model, values[field])
                        inherited = (
                            source.security_context
                            if source and source.user_id == user_id
                            else None
                        )
                        break
            if parent:
                inherited = parent.security_context
            tenant = (
                (inherited or {}).get("company_id")
                or getattr(row, "organization_id", None)
                or company(user)
            )
            if inherited and not db.info.get("ai_request_context"):
                previous = getattr(user, "organization_id", None)
                user.organization_id = tenant
                try:
                    verify(db, user, inherited)
                    row.security_context = seal(
                        db,
                        user,
                        operation(row),
                        session_id=inherited.get("session_id"),
                        tenant=tenant,
                    )
                finally:
                    if previous is None:
                        user.__dict__.pop("organization_id", None)
                    else:
                        user.organization_id = previous
            else:
                row.security_context = seal(db, user, operation(row), tenant=tenant)
            if hasattr(row, "organization_id"):
                row.organization_id = tenant


def bind_http(db, user, request, claims):
    info = {
        "user_id": user.id,
        "company_id": company(user),
        "session_id": getattr(user, "_suite_session_id", None),
        "correlation_id": getattr(request.state, "request_id", None) or uuid4().hex,
    }
    ai_path = request.url.path.startswith(
        (
            "/api/v1/ai-operator",
            "/api/v1/ai-agents",
            "/api/v1/ai/",
            "/api/v1/ai-copilot",
        )
    )
    delegated = claims.get("ai_origin")
    if ai_path and info["session_id"] is None:
        raise HTTPException(401, "Sign in again before using AI tools")
    if delegated:
        if (
            delegated.get("company_id") != info["company_id"]
            or delegated.get("path") != request.url.path
            or delegated.get("method") != request.method
        ):
            raise HTTPException(403, "AI delegated request scope mismatch")
        boundary(request.method, request.url.path)
    info["is_ai"] = ai_path or bool(delegated)
    from app.core.audit_context import context

    audit_context = context.get()
    if audit_context is not None:
        audit_context["ai_context"] = info
    previous = db.info.get("ai_request_context")
    db.info["ai_request_context"] = info
    token = None

    def cleanup():
        if previous is None:
            db.info.pop("ai_request_context", None)
        else:
            db.info["ai_request_context"] = previous

    return cleanup


def delegated_token(authorization, method, path, payload=None):
    from app.core.security import verify_access_token, create_access_token

    claims = verify_access_token(authorization.partition(" ")[2])
    if not claims:
        raise HTTPException(401, "Valid initiating AI session required")
    origin = ORIGIN.get() or claims.get("ai_origin")
    if not origin or not claims.get("sid"):
        raise HTTPException(
            401, "AI delegation requires a bound initiating session and company"
        )
    boundary(method, path)
    return "Bearer " + create_access_token(
        claims["sub"],
        expires_delta=timedelta(minutes=1),
        session_id=int(claims["sid"]),
        ai_origin={
            "company_id": origin["company_id"],
            "method": method,
            "path": path,
            "arguments": digest(
                __import__("httpx").QueryParams(payload or {}).multi_items()
                if method == "GET"
                else payload
            ),
        },
    )


def history_guard(db, user, row):
    verify(db, user, row.security_context, history=True)
    if getattr(row, "agent_id", None):
        from app.ai_agents.services.advanced_security import AiAgentPermissionService

        if not AiAgentPermissionService(db).can_use_agent(user, row.agent_id):
            raise HTTPException(403, "AI agent access revoked")
    kind = getattr(row, "related_entity_type", None)
    ident = getattr(row, "related_entity_id", None)
    if kind and ident and str(ident).isdigit():
        from app.shared.gateway import read_record

        module = MODULES.get(str(getattr(row, "module", "")).upper())
        aliases = {
            "crm_lead": "lead",
            "crm_deal": "deal",
            "pms_project": "project",
            "pms_task": "task",
        }
        entity = aliases.get(kind, kind)
        from app.shared.contracts import RECORDS

        if (module, entity) in RECORDS:
            source_record_access(db, user, module, entity, int(ident))


@event.listens_for(Session, "do_orm_execute")
def isolate_history(execution):
    if not execution.is_select:
        return
    db = execution.session
    ctx = db.info.get("ai_request_context")
    if not ctx or db.info.get("ai_fingerprinting"):
        return
    entities = {
        d.get("entity")
        for d in getattr(execution.statement, "column_descriptions", [])
        if isinstance(d, dict)
    }
    if not any(
        getattr(entity, "__name__", "")
        in {"AiConversation", "AiMessage", "AssistantConversation", "AssistantMessage"}
        for entity in entities
    ):
        return
    from app.models.user import User
    from app.ai_agents.models import AiConversation, AiMessage
    from app.ai_operator.assistant_models import AssistantConversation, AssistantMessage
    from sqlalchemy.orm import with_loader_criteria
    from sqlalchemy import and_

    with db.no_autoflush:
        # Core identity read prevents recursion into this event.
        user = db.identity_map.get((User, (ctx["user_id"],), None))
        if not user:
            return
        stamp = ctx.get("fingerprint")
        if stamp is None:
            db.info["ai_fingerprinting"] = True
            try:
                stamp = fingerprint(db, user, ctx["company_id"])
                ctx["fingerprint"] = stamp
            finally:
                db.info.pop("ai_fingerprinting", None)
    if stamp is None:
        return
    filters = []
    for model in (AiConversation, AssistantConversation):
        clause = and_(
            model.user_id == user.id,
            model.organization_id == ctx["company_id"],
            model.security_context["fingerprint"].as_string() == stamp,
        )
        filters.append(with_loader_criteria(model, clause, include_aliases=True))
    for model, parent in (
        (AiMessage, AiConversation),
        (AssistantMessage, AssistantConversation),
    ):
        table = parent.__table__
        visible = select(table.c.id).where(
            table.c.user_id == user.id,
            table.c.organization_id == ctx["company_id"],
            table.c.security_context["fingerprint"].as_string() == stamp,
        )
        filters.append(
            with_loader_criteria(
                model, model.conversation_id.in_(visible), include_aliases=True
            )
        )
    execution.statement = execution.statement.options(*filters)


@event.listens_for(Session, "before_flush")
def acl_epoch(db, flush_context, instances):
    """Conservatively invalidate cached AI context when record access changes."""
    from sqlalchemy import inspect as state_of
    from app.shared.models import ServicePolicy
    from app.models.company import Company

    affected = set()
    subjects = {}
    fields = {
        "organization_id",
        "owner_user_id",
        "assignee_user_id",
        "assignee_user_ids",
        "assigned_team_id",
        "branch_id",
        "department_id",
        "reporting_manager_id",
        "deleted_at",
    }
    for row in db.dirty | db.deleted:
        source = type(row).__module__
        if not (
            source.startswith(("app.apps.crm.", "app.apps.project_management."))
            or source == "app.models.employee"
        ):
            continue
        state = state_of(row)
        if row in db.deleted or any(
            name in state.attrs and state.attrs[name].history.has_changes()
            for name in fields
        ):
            tenant = (
                getattr(row, "organization_id", None)
                or (db.info.get("ai_request_context") or {}).get("company_id")
                or 1
            )
            affected.add(tenant)
            subjects[tenant] = (
                getattr(row, "updated_by_user_id", None)
                or getattr(row, "owner_user_id", None)
                or getattr(row, "assignee_user_id", None)
                or getattr(row, "user_id", None)
            )
    for tenant in sorted(affected):
        if (
            not db.connection()
            .execute(
                select(Company.__table__.c.id).where(Company.__table__.c.id == tenant)
            )
            .first()
        ):
            continue
        db.connection().execute(
            select(Company.__table__.c.id)
            .where(Company.__table__.c.id == tenant)
            .with_for_update()
        )
        table = ServicePolicy.__table__
        key = f"company:{tenant}:ai_acl_epoch"
        row = (
            db.connection()
            .execute(
                select(table.c.id, table.c.version).where(
                    table.c.scope_key == key, table.c.kind == "ai_acl_epoch"
                )
            )
            .first()
        )
        if row:
            db.connection().execute(
                table.update()
                .where(table.c.id == row.id)
                .values(version=row.version + 1)
            )
        else:
            actor = (db.info.get("ai_request_context") or {}).get(
                "user_id"
            ) or subjects.get(tenant)
            if actor:
                db.connection().execute(
                    table.insert().values(
                        scope_key=key,
                        organization_id=tenant,
                        kind="ai_acl_epoch",
                        values_json={},
                        version=1,
                        updated_by=actor,
                    )
                )
        if db.info.get("ai_request_context"):
            db.info["ai_request_context"].pop("fingerprint", None)


def visible_history(db, user, rows):
    """Retain historical records while excluding stale authorization contexts."""
    visible = []
    for row in rows:
        try:
            verify(db, user, row.security_context, history=True)
        except HTTPException:
            continue
        visible.append(row)
    return visible


@event.listens_for(Session, "do_orm_execute")
def bulk_acl_epoch(execution):
    """Bulk ORM writes also invalidate cached scope; never rely only on row hooks."""
    if not (execution.is_update or execution.is_delete):
        return
    db = execution.session
    ctx = db.info.get("ai_request_context") or {}
    table = getattr(execution.statement, "table", None)
    name = getattr(table, "name", "")
    if not ctx.get("user_id") or not name.startswith(("crm_", "pms_")):
        return
    acl_fields = {
        "organization_id",
        "owner_user_id",
        "assignee_user_id",
        "assignee_user_ids",
        "assigned_team_id",
        "branch_id",
        "department_id",
        "reporting_manager_id",
        "deleted_at",
        "user_id",
        "role",
    }
    if execution.is_update:
        changed = {
            getattr(k, "name", str(k))
            for k in (getattr(execution.statement, "_values", None) or {})
        }
        if not changed.intersection(acl_fields):
            return
    elif name not in {
        "crm_leads",
        "crm_deals",
        "crm_companies",
        "crm_contacts",
        "crm_tasks",
        "pms_projects",
        "pms_workspaces",
        "pms_tasks",
    } and not any(part in name for part in ("member", "team")):
        return
    from app.shared.models import ServicePolicy
    from app.models.company import Company

    tenant = ctx["company_id"]
    db.connection().execute(
        select(Company.__table__.c.id)
        .where(Company.__table__.c.id == tenant)
        .with_for_update()
    )
    table = ServicePolicy.__table__
    key = f"company:{tenant}:ai_acl_epoch"
    row = (
        db.connection()
        .execute(
            select(table.c.id, table.c.version).where(
                table.c.scope_key == key, table.c.kind == "ai_acl_epoch"
            )
        )
        .first()
    )
    if row:
        db.connection().execute(
            table.update().where(table.c.id == row.id).values(version=row.version + 1)
        )
    else:
        db.connection().execute(
            table.insert().values(
                scope_key=key,
                organization_id=tenant,
                kind="ai_acl_epoch",
                values_json={},
                version=1,
                updated_by=ctx["user_id"],
            )
        )
    ctx.pop("fingerprint", None)


def execution_budget(db, user, run):
    """Check elapsed execution across checkpoints; exclude draft review/queue wait."""
    now = datetime.now(timezone.utc)
    data = run.result or {}
    started = data.get("_security_execution_started")
    if (
        started
        and (now - utc(started)).total_seconds()
        > limits(db, company(user))["max_seconds"]
    ):
        raise HTTPException(
            409, "AI execution time budget exhausted; prepare a fresh preview"
        )
    if not started:
        run.result = {**data, "_security_execution_started": now.isoformat()}


def handoff_guard(db, user, row, recipient=False):
    """Sharing an AI note never transfers source-record authorization."""
    from app.models.user import User
    from app.ai_agents.models import AiConversation
    from app.shared.gateway import read_record
    from app.shared.contracts import RECORDS, authorize

    if row.organization_id != company(user):
        raise HTTPException(404, "Handoff note not found")
    if not recipient and user.id not in (row.created_by, row.assigned_to):
        raise HTTPException(404, "Handoff note not found")
    creator = db.get(User, row.created_by)
    if not creator:
        raise HTTPException(404, "Handoff initiator unavailable")
    previous = getattr(creator, "organization_id", None)
    creator.organization_id = row.organization_id
    try:
        verify(db, creator, row.security_context, history=True)
    finally:
        if previous is None:
            creator.__dict__.pop("organization_id", None)
        else:
            creator.organization_id = previous
    module = MODULES.get(str(row.module).upper())
    if not module:
        raise HTTPException(403, "Unsupported handoff module")
    authorize(db, user, company(user), module, "view")
    # Conversation summaries without a recheckable source remain owner-private.
    if row.conversation_id:
        source = (
            db.connection()
            .execute(
                AiConversation.__table__.select().where(
                    AiConversation.__table__.c.id == row.conversation_id
                )
            )
            .mappings()
            .first()
        )
        if (
            not source
            or source["user_id"] != row.created_by
            or source["organization_id"] != company(user)
        ):
            raise HTTPException(404, "Handoff conversation unavailable")
    entity = {
        "crm_lead": "lead",
        "crm_deal": "deal",
        "pms_task": "task",
        "pms_project": "project",
    }.get(row.related_entity_type, row.related_entity_type)
    if (
        row.related_entity_id
        and str(row.related_entity_id).isdigit()
        and (module, entity) in RECORDS
    ):
        with scoped(db, user, module):
            source_record_access(db, user, module, entity, int(row.related_entity_id))
    elif user.id != row.created_by:
        raise HTTPException(
            403, "Sharing this note needs a supported authorized source record"
        )


def source_record_access(db, user, module, entity, ident):
    """Use scoped native services for AI source rechecks, without nested HTTP writes/audits."""
    from app.shared.contracts import RECORDS, authorize

    contract = RECORDS.get((module, entity))
    if not contract:
        raise HTTPException(403, "Unsupported source record")
    authorize(db, user, company(user), module, "view", contract.permission)
    with scoped(db, user, module):
        if (module, entity) == ("crm", "lead"):
            from app.ai_agents.adapters.crm_ai_adapter import CrmAiAdapter

            return CrmAiAdapter(db)._get_lead(user, ident)
        if module == "project_management":
            from app.apps.project_management.access import (
                get_project_for_action,
                get_task_project_for_action,
            )

            if entity == "project":
                return get_project_for_action(db, ident, user, "browse")
            if entity == "task":
                return get_task_project_for_action(db, ident, user, "browse")
        from app.shared.gateway import read_record

        return read_record(db, user, company(user), module, entity, ident)
