"""Canonical API gateway and SDK. No caller-supplied URL, SQL or executable code."""

import asyncio
import hashlib
import json
from datetime import timedelta
import httpx
from fastapi import HTTPException
from app.core.security import create_access_token
from app.shared.contracts import RECORDS, authorize


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def business_snapshot(value, depth=0):
    """Stable approval data excludes credentials and short-lived access URLs."""
    if depth > 15:
        raise HTTPException(422, "Business snapshot is too deeply nested")
    if isinstance(value, dict):
        return {
            key: business_snapshot(item, depth + 1)
            for key, item in value.items()
            if not any(
                word in key.lower()
                for word in (
                    "token",
                    "secret",
                    "password",
                    "session",
                    "signature",
                    "recovery_code",
                )
            )
        }
    if isinstance(value, list):
        if len(value) > 1000:
            raise HTTPException(422, "Business snapshot exceeds approval limits")
        return [business_snapshot(item, depth + 1) for item in value]
    if isinstance(value, str) and ("?token=" in value or "&token=" in value):
        return "[authorized-file-reference]"
    return value


async def canonical(user, company, method, path, payload=None):
    from app.main import app

    token = create_access_token(str(user.id), expires_delta=timedelta(minutes=1))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://suite-internal",
        follow_redirects=False,
        headers={
            "Authorization": "Bearer " + token,
            "X-Suite-Organization": str(company),
        },
    ) as client:
        response = await client.request(
            method,
            "/api/v1" + path,
            params=payload if method == "GET" else None,
            json=payload if method != "GET" else None,
        )
    if not 200 <= response.status_code < 300:
        raise HTTPException(
            (
                response.status_code
                if response.status_code in {400, 401, 403, 404, 409, 422}
                else 502
            ),
            f"Canonical API rejected action (HTTP {response.status_code})",
        )
    return response.json()


def read_record(db, user, company, module, entity, entity_id):
    contract = RECORDS.get((module, entity))
    if not contract:
        raise HTTPException(422, "This entity has no authorized record adapter")
    authorize(db, user, company, module, "view", contract.permission)
    from app.enterprise.controls import governance_check

    governance_check(db, user, company, module, entity)
    if type(entity_id) is not int or entity_id < 1:
        raise HTTPException(422, "A positive record identifier is required")
    return asyncio.run(
        canonical(user, company, "GET", contract.read_path.format(id=entity_id))
    )


def invoke_tool(db, user, company, name, payload, record_id=None):
    from app.ai_operator.suite_tools import TOOLS, validate_payload

    tool = TOOLS.get(name)
    if not tool:
        raise HTTPException(
            422, "Action is not registered in the approved tool catalog"
        )
    module = {
        "PMS": "project_management",
        "HRMS": "hrms",
        "CRM": "crm",
        "SRM": "srm",
        "FAM": "fam",
    }.get(tool.module, tool.module.lower())
    authorize(
        db,
        user,
        company,
        module,
        (
            "view"
            if tool.method == "GET"
            else "create" if tool.method == "POST" else "edit"
        ),
    )
    if not user.is_superuser and tool.permissions:
        from app.access.service import resolved_grants, policy_for

        policy = policy_for(db, user, company)
        names = (
            set(resolved_grants(db, policy).get(module, {}).get("permissions", []))
            if policy
            else set()
        )
        if not names.intersection(tool.permissions):
            raise HTTPException(403, "Action native permission required")
    validate_payload(tool, payload)
    if "{record_id}" in tool.path and (type(record_id) is not int or record_id < 1):
        raise HTTPException(422, "Select the authorized target record")
    # High-level PMS plans have separate human-approval flows; retain those.
    if tool.project_target or tool.optional_project:
        raise HTTPException(
            422, "Use the existing PMS approval workbench for this tool"
        )
    return asyncio.run(
        canonical(
            user, company, tool.method, tool.path.format(record_id=record_id), payload
        )
    )


class ModuleServices:
    """Bound tenant/actor context. Construct from an authenticated module request."""

    def __init__(self, db, actor, company, module):
        authorize(db, actor, company, module)
        self.db, self.actor, self.company, self.module = db, actor, company, module

    def emit(self, event, entity, entity_id, request_key, data=None):
        from app.shared.runtime import emit

        return emit(
            self.db,
            self.actor,
            self.company,
            self.module,
            event,
            entity,
            entity_id,
            request_key,
            data or {},
        )

    def notify(self, entity, entity_id, recipient_id, title, message):
        from app.shared.communications import notify

        return notify(
            self.db,
            self.actor,
            self.company,
            self.module,
            entity,
            entity_id,
            recipient_id,
            title,
            message,
        )

    def read(self, entity, entity_id):
        return read_record(
            self.db, self.actor, self.company, self.module, entity, entity_id
        )

    def settings(self):
        from app.shared.settings import effective

        return effective(self.db, self.company, self.module)

    def integration(self, connection_id, operation, payload):
        from app.shared.integrations import invoke

        return invoke(
            self.db,
            self.actor,
            self.company,
            self.module,
            connection_id,
            operation,
            payload,
        )

    def ai(self, agent, tool, payload):
        from app.ai_agents.tools.ai_tool_execution_service import AiToolExecutionService

        authorize(self.db, self.actor, self.company, "ai", "create", "ai_assistant")
        self._ai_budget()
        from app.ai_agents.tools.ai_tool_registry_service import AiToolRegistryService
        from app.ai_agents.services.advanced_security import AiUsageService

        definition = AiToolRegistryService(self.db).get_tool(tool)
        expected = {
            "project_management": "PMS",
            "crm": "CRM",
            "hrms": "HRMS",
            "srm": "SRM",
            "fam": "FAM",
        }.get(self.module, self.module.upper())
        if not definition or definition.module != expected:
            raise HTTPException(403, "AI tool is outside the bound module")
        AiUsageService(self.db).check_limits(
            user=self.actor, agent=None, module=expected
        )
        from app.access.service import background_scope

        previous = getattr(self.actor, "organization_id", None)
        self.actor.organization_id = self.company
        try:
            with background_scope(self.db, self.actor, self.module):
                return AiToolExecutionService(self.db).execute_tool(
                    user=self.actor, agent_code=agent, tool_name=tool, input=payload
                )
        finally:
            self.actor.organization_id = previous

    def ai_draft(self, provider, prompt, schema, entity, entity_id):
        """Any module can use the existing provider gateway for a structured draft."""
        authorize(self.db, self.actor, self.company, "ai", "create", "ai_assistant")
        self._ai_budget()
        if (
            not isinstance(prompt, str)
            or not 1 <= len(prompt) <= 6000
            or not isinstance(schema, dict)
            or len(str(schema)) > 16000
        ):
            raise HTTPException(
                422, "Bounded prompt and structured output schema required"
            )
        from app.ai_operator.provider_scope import resolve_provider
        from app.ai_operator.providers import generate_json
        from app.ai_operator.suite_tools import minimize
        from app.ai_agents.services.advanced_security import AiUsageService

        previous = getattr(self.actor, "organization_id", None)
        self.actor.organization_id = self.company
        try:
            AiUsageService(self.db).check_limits(
                user=self.actor, agent=None, module=self.module
            )
            record = minimize(self.read(entity, entity_id))
            config = resolve_provider(self.db, self.actor, provider)
            if not config or not config.enabled:
                raise HTTPException(
                    503, "Configure and verify the company AI provider first"
                )
            return generate_json(
                self.db,
                self.actor,
                config,
                prompt=prompt
                + "\nAuthorized record context:\n"
                + json.dumps(record, default=str),
                schema=schema,
                purpose="shared_draft",
            )
        finally:
            self.actor.organization_id = previous

    def _ai_budget(self):
        from app.enterprise.controls import quota

        quota(self.db, self.company, "ai_requests")
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import select, func
        from app.models.company import Company
        from app.ai_agents.models import AiUsageEvent
        from app.shared.settings import effective

        self.db.query(Company).filter_by(id=self.company).with_for_update().one()
        table = AiUsageEvent.__table__
        count = (
            self.db.connection()
            .execute(
                select(func.count())
                .select_from(table)
                .where(
                    table.c.company_id == self.company,
                    table.c.module == self.module,
                    table.c.event_type == "shared_request",
                    table.c.created_at
                    >= datetime.now(timezone.utc) - timedelta(days=1),
                )
            )
            .scalar()
        )
        if (
            count
            >= effective(self.db, self.company, self.module)["values"][
                "ai_daily_requests"
            ]
        ):
            raise HTTPException(429, "Company/module shared AI request budget exceeded")
        self.db.add(
            AiUsageEvent(
                company_id=self.company,
                user_id=self.actor.id,
                module=self.module,
                event_type="shared_request",
            )
        )
        self.db.flush()

    def approval(self, entity, entity_id, approvers, title, request_key, mode="all"):
        from app.shared.runtime import request_approval

        return request_approval(
            self.db,
            self.actor,
            self.company,
            self.module,
            entity,
            entity_id,
            approvers,
            title,
            request_key,
            mode,
        )

    def email(self, entity, entity_id, recipient_id, subject, body):
        from app.shared.communications import notify

        return notify(
            self.db,
            self.actor,
            self.company,
            self.module,
            entity,
            entity_id,
            recipient_id,
            subject,
            body,
            ["email"],
        )

    def validate_custom_fields(self, values, record_id=None):
        from app.apps.customization.services.validation import (
            validate_field_value,
            evaluate_condition,
        )
        from app.apps.customization.models import (
            CustomizationField,
            CustomizationValidationRule,
        )

        authorize(self.db, self.actor, self.company, self.module, "edit")
        # Global schema metadata must not disappear behind a business-data scope.
        # Uniqueness/relationship checks need a module-owned tenant adapter.
        table = CustomizationField.__table__
        fields = (
            self.db.connection()
            .execute(
                table.select().where(
                    table.c.module_name == self.module, table.c.visible.is_(True)
                )
            )
            .mappings()
            .all()
        )
        if set(values) - {f["field_api_name"] for f in fields}:
            raise HTTPException(422, "Unknown custom field")
        for metadata in fields:
            field = CustomizationField(**metadata)
            if field.unique or field.field_type in {
                "lookup",
                "user_lookup",
                "file",
                "rollup",
            }:
                raise HTTPException(
                    422, "This field requires a tenant-aware relationship adapter"
                )
            if field.field_api_name in values and not field.editable:
                raise HTTPException(403, "Custom field is read-only")
            validate_field_value(
                self.db,
                field,
                values.get(field.field_api_name, field.default_value),
                record_id,
            )
        table = CustomizationValidationRule.__table__
        for rule in (
            self.db.connection()
            .execute(
                table.select().where(
                    table.c.module_name == self.module, table.c.active.is_(True)
                )
            )
            .mappings()
        ):
            if evaluate_condition(rule["condition_json"], values):
                raise HTTPException(422, rule["error_message"])

    def documents(self, entity, entity_id):
        from app.shared.models import ServiceDocument

        self.read(entity, entity_id)
        return (
            self.db.query(ServiceDocument)
            .filter_by(
                organization_id=self.company,
                module_key=self.module,
                entity_type=entity,
                entity_id=entity_id,
            )
            .all()
        )

    def form(self, definition):
        from app.forms.router import create, Create
        from app.forms.settings import FormDefinition

        authorize(self.db, self.actor, self.company, "forms", "create")
        authorize(self.db, self.actor, self.company, self.module, "create")
        key = "pms" if self.module == "project_management" else self.module
        return create(
            Create(
                module_key=key, definition=FormDefinition.model_validate(definition)
            ),
            self.db,
            self.actor,
        )
