"""Existing governed AI gateway, bounded inputs and untrusted typed output."""

import json
from copy import copy
from fastapi import HTTPException
from app.apps.power_apps.integrations.contracts import AIInput, IntegrationFailure
from app.apps.power_apps.integrations.registry import AI_TASKS
from app.apps.power_apps.runtime_triggers import validate_schema, schema_check


def execute(db, user, conn, action, data):
    from app.ai_agents.security import _require_ai_access
    from app.ai_agents.services.advanced_security import (
        AiSecuritySettingsService,
        AiUsageService,
        AiDataRedactionService,
    )
    from app.ai_operator.models import OperatorProvider
    from app.ai_operator.providers import generate_json
    from app.access.service import check_background_access, effective_objects
    from app.apps.business_os.services.module_service import assert_module_enabled

    data = AIInput.model_validate(data)
    if action not in AI_TASKS:
        raise IntegrationFailure("action", "Unsupported AI action")
    check_background_access(db, user, "ai", "view")
    ai_user = copy(user)
    if getattr(user, "_suite_grants", None) is not None:
        ai_user._suite_permission_objects = effective_objects(
            db, user._suite_grants, "ai"
        )
    _require_ai_access(ai_user)
    assert_module_enabled(db, "ai", conn.organization_id)
    AiSecuritySettingsService(db).ensure_enabled(user=user, module="CROSS")
    AiUsageService(db).check_limits(user=user, agent=None, module="CROSS")
    provider = (
        db.query(OperatorProvider)
        .filter_by(
            scope_key=f"company:{conn.organization_id}",
            provider=conn.config.get("provider", "openai"),
            enabled=True,
            data_sharing_allowed=True,
        )
        .first()
    )
    if not provider:
        raise IntegrationFailure(
            "configuration",
            "Configure an enabled company AI provider with explicit data-sharing approval",
        )
    if action in {"classify", "route"}:
        if (
            not data.categories
            or len(set(data.categories)) != len(data.categories)
            or any(not x or len(x) > 100 for x in data.categories)
        ):
            raise IntegrationFailure(
                "schema", "Provide distinct allowed classification labels"
            )
        schema = {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": data.categories},
                "confidence": {"type": "number"},
            },
            "required": ["category", "confidence"],
            "additionalProperties": False,
        }
    elif action == "sentiment":
        schema = {
            "type": "object",
            "properties": {
                "sentiment": {
                    "type": "string",
                    "enum": ["positive", "neutral", "negative", "mixed"],
                },
                "confidence": {"type": "number"},
            },
            "required": ["sentiment", "confidence"],
            "additionalProperties": False,
        }
    elif action == "action_items":
        schema = {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "string"}, "maxItems": 50}
            },
            "required": ["items"],
            "additionalProperties": False,
        }
    elif action in {"extract", "normalize", "json", "form"}:
        if not data.output_schema:
            raise IntegrationFailure(
                "schema", "This AI action requires an explicit bounded output schema"
            )
        schema = data.output_schema
    else:
        schema = {
            "type": "object",
            "properties": {"text": {"type": "string", "maxLength": 16000}},
            "required": ["text"],
            "additionalProperties": False,
        }
    validate_schema(schema)
    bounded_provider = copy(provider)
    bounded_provider.max_tokens = min(provider.max_tokens, data.token_budget)
    outbound = AiDataRedactionService().redact_for_ai(
        user,
        "CROSS",
        {
            "task": AI_TASKS[action],
            "input": data.input,
            "instruction": data.instruction,
            "target_language": data.target_language,
            "document_b": data.document_b,
        },
    )
    # Atomic tenant budget accounting is supplied by the existing gateway governance.
    AiUsageService(db).record_event(
        user=user, agent_id=None, module="CROSS", event_type="power_apps_action"
    )
    db.commit()

    class ValidatedOutput:
        @staticmethod
        def model_validate(value):
            schema_check(value, schema)
            return value

    try:
        result = generate_json(
            db,
            user,
            bounded_provider,
            prompt=json.dumps(outbound),
            schema=schema,
            purpose="power_apps_action",
            output_type=ValidatedOutput,
            usage_scope=f"company:{conn.organization_id}",
            module="POWER_APPS",
        )
        schema_check(result, schema)
        if "confidence" in result and not 0 <= result["confidence"] <= 1:
            raise ValueError("Confidence must be 0–1")
        db.commit()
        return result
    except HTTPException:
        db.commit()
        raise IntegrationFailure(
            "ai_provider", "AI provider request failed; no fallback was generated"
        ) from None
    except (ValueError, TypeError, KeyError):
        db.commit()
        raise IntegrationFailure(
            "ai_output",
            "AI output did not match the requested schema; no fallback was generated",
        ) from None
