from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.apps.automation.models import (
    AutomationAction,
    AutomationApprovalRequest,
    AutomationCondition,
    AutomationExecutionLog,
    AutomationWorkflow,
)
from app.models.notification import Notification
from app.models.user import User


ALLOWED_OPERATORS = {
    "equals",
    "not_equals",
    "not equals",
    "contains",
    "greater_than",
    "greater than",
    "greater_or_equal",
    "less_than",
    "less than",
    "less_or_equal",
    "between",
    "is_empty",
    "is empty",
    "is_not_empty",
    "is not empty",
    "owner_is",
    "owner is",
    "role_is",
    "role is",
    "stage_is",
    "stage is",
    "amount_threshold",
    "margin_threshold",
    "in",
    "not_in",
    "exists",
    "not_exists",
}

ALLOWED_ACTION_TYPES = {
    "send_notification",
    "send_email",
    "send_whatsapp_placeholder",
    "send_sms_placeholder",
    "create_task",
    "update_field",
    "submit_approval",
    "call_webhook",
    "create_related_record",
    "create_timeline_event",
    "assign_owner",
    "add_tag",
    "escalate_record",
}

ACTION_REQUIRED_FIELDS = {
    "send_notification": {"title"},
    "send_email": {"template_id"},
    "send_whatsapp_placeholder": {"template_id"},
    "send_sms_placeholder": {"template_id"},
    "create_task": {"title"},
    "update_field": {"field", "value"},
    "submit_approval": {"rule_id"},
    "call_webhook": {"webhook_endpoint_id"},
    "create_related_record": {"record_type"},
    "create_timeline_event": {"title"},
    "assign_owner": {"user_id"},
    "add_tag": {"tag"},
    "escalate_record": {"reason"},
}


def organization_id_for(user: User) -> int | None:
    return getattr(user, "organization_id", None)


def validate_condition_schema(condition: dict[str, Any]) -> None:
    if not isinstance(condition, dict):
        raise HTTPException(status_code=400, detail="Automation conditions must be JSON objects")
    operator = condition.get("operator", "equals")
    if operator not in ALLOWED_OPERATORS:
        raise HTTPException(status_code=400, detail=f"Unsupported condition operator: {operator}")
    if operator not in {"exists", "not_exists", "is_empty", "is empty", "is_not_empty", "is not empty"} and "value" not in condition:
        raise HTTPException(status_code=400, detail="Condition value is required")
    if "field" not in condition:
        raise HTTPException(status_code=400, detail="Condition field is required")


def validate_action_schema(action: dict[str, Any]) -> str:
    if not isinstance(action, dict):
        raise HTTPException(status_code=400, detail="Automation actions must be JSON objects")
    action_type = action.get("type") or action.get("action_type")
    if action_type not in ALLOWED_ACTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported action type: {action_type}")
    missing = ACTION_REQUIRED_FIELDS.get(action_type, set()) - set(action.keys())
    if missing:
        raise HTTPException(status_code=400, detail=f"Action {action_type} missing required fields: {', '.join(sorted(missing))}")
    if action_type == "call_webhook" and action.get("target_url"):
        raise HTTPException(status_code=400, detail="Arbitrary webhook URLs are not allowed in actions; reference a configured endpoint")
    return str(action_type)


def validate_workflow_payload(conditions: list[dict[str, Any]], actions: list[dict[str, Any]]) -> None:
    for condition in conditions:
        validate_condition_schema(condition)
    for action in actions:
        validate_action_schema(action)


def _value_for(record: dict[str, Any], path: str) -> Any:
    value: Any = record
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def evaluate_condition(condition: dict[str, Any], record: dict[str, Any]) -> bool:
    validate_condition_schema(condition)
    actual = _value_for(record, str(condition["field"]))
    expected = condition.get("value")
    operator = condition.get("operator", "equals")
    operator = operator.replace(" ", "_")
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        return str(expected).lower() in str(actual or "").lower()
    if operator == "greater_than":
        return float(actual or 0) > float(expected)
    if operator == "greater_or_equal":
        return float(actual or 0) >= float(expected)
    if operator == "less_than":
        return float(actual or 0) < float(expected)
    if operator == "less_or_equal":
        return float(actual or 0) <= float(expected)
    if operator == "in":
        return actual in (expected or [])
    if operator == "not_in":
        return actual not in (expected or [])
    if operator == "between":
        bounds = expected or []
        if len(bounds) != 2:
            raise HTTPException(status_code=400, detail="Between condition requires a two-value list")
        return float(bounds[0]) <= float(actual or 0) <= float(bounds[1])
    if operator == "is_empty":
        return actual in (None, "", [], {})
    if operator == "is_not_empty":
        return actual not in (None, "", [], {})
    if operator in {"owner_is", "role_is", "stage_is"}:
        return actual == expected
    if operator in {"amount_threshold", "margin_threshold"}:
        return float(actual or 0) >= float(expected)
    if operator == "exists":
        return actual is not None
    if operator == "not_exists":
        return actual is None
    return False


def evaluate_conditions(conditions: list[dict[str, Any]], record: dict[str, Any]) -> bool:
    return all(evaluate_condition(condition, record) for condition in conditions)


def _serialize_log(log: AutomationExecutionLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "workflow_id": log.workflow_id,
        "module_name": log.module_name,
        "record_type": log.record_type,
        "record_id": log.record_id,
        "trigger_type": log.trigger_type,
        "status": log.status,
        "depth": log.depth,
        "request_json": log.request_json,
        "result_json": log.result_json,
        "error_message": log.error_message,
        "created_at": log.created_at.isoformat() if log.created_at else None,
    }


def _action_result(db: Session, action: AutomationAction, context: dict[str, Any], user: User) -> dict[str, Any]:
    payload = action.action_json or {}
    action_type = validate_action_schema(payload)
    if action_type == "send_notification":
        db.add(Notification(
            company_id=None,
            user_id=payload.get("user_id") or user.id,
            title=payload["title"],
            message=payload.get("message", "Automation notification"),
            module=context.get("module_name") or "automation",
            event_type="automation.action",
            related_entity_type=context.get("record_type"),
            related_entity_id=context.get("record_id"),
            action_url=payload.get("action_url"),
            priority=payload.get("priority", "normal"),
        ))
        return {"type": action_type, "status": "notification_created"}
    if action_type == "submit_approval":
        request = AutomationApprovalRequest(
            organization_id=organization_id_for(user),
            rule_id=payload["rule_id"],
            module_name=context.get("module_name") or "automation",
            record_type=context.get("record_type") or "record",
            record_id=context.get("record_id") or 0,
            status="pending",
            submitted_by=user.id,
            payload_json={"source": "automation", "context": context},
            history_json=[{"status": "pending", "at": datetime.now(timezone.utc).isoformat(), "by": user.id}],
        )
        db.add(request)
        db.flush()
        return {"type": action_type, "status": "approval_requested", "approval_request_id": request.id}
    if action_type == "call_webhook":
        return {"type": action_type, "status": "webhook_test_logged", "webhook_endpoint_id": payload.get("webhook_endpoint_id")}
    return {"type": action_type, "status": "simulated", "payload": payload}


def execute_workflow(db: Session, workflow: AutomationWorkflow, context: dict[str, Any], user: User) -> AutomationExecutionLog:
    conditions = [item.condition_json for item in db.query(AutomationCondition).filter(AutomationCondition.workflow_id == workflow.id).order_by(AutomationCondition.order_index).all()]
    actions = db.query(AutomationAction).filter(AutomationAction.workflow_id == workflow.id).order_by(AutomationAction.order_index).all()
    depth = int(context.get("depth") or 0)
    log = AutomationExecutionLog(
        organization_id=organization_id_for(user),
        workflow_id=workflow.id,
        module_name=context.get("module_name") or workflow.module_name,
        record_type=context.get("record_type") or workflow.record_type,
        record_id=context.get("record_id"),
        trigger_type=context.get("trigger_type") or workflow.trigger_type,
        status="success",
        depth=depth,
        request_json=context,
        created_by=user.id,
    )
    db.add(log)
    try:
        if depth > int(workflow.max_execution_depth or 5):
            raise HTTPException(status_code=400, detail="Automation recursion depth exceeded")
        if not evaluate_conditions(conditions, context.get("record") or {}):
            log.status = "skipped"
            log.result_json = {"conditions_matched": False, "actions": []}
            return log
        results = [_action_result(db, action, context, user) for action in actions]
        log.result_json = {"conditions_matched": True, "actions": results}
        return log
    except HTTPException as exc:
        log.status = "failed"
        log.error_message = str(exc.detail)
        log.result_json = {"conditions_matched": False, "actions": []}
        return log
    except Exception as exc:  # pragma: no cover - defensive logging path
        log.status = "failed"
        log.error_message = str(exc)
        log.result_json = {"conditions_matched": False, "actions": []}
        return log


def retry_execution_log(db: Session, log: AutomationExecutionLog, user: User) -> AutomationExecutionLog:
    if log.status not in {"failed", "error"}:
        raise HTTPException(status_code=400, detail="Only failed automation executions can be retried")
    workflow = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == log.workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found for retry")
    context = dict(log.request_json or {})
    context["depth"] = int(log.depth or 0) + 1
    return execute_workflow(db, workflow, context, user)


def serialize_log(log: AutomationExecutionLog) -> dict[str, Any]:
    return _serialize_log(log)
