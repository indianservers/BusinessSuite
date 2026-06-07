from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.apps.automation.models import (
    AutomationAction,
    AutomationApprovalRequest,
    AutomationApprovalRule,
    AutomationApprovalStep,
    AutomationAssignmentRule,
    AutomationBlueprint,
    AutomationBlueprintStage,
    AutomationBlueprintTransition,
    AutomationCadence,
    AutomationCadenceStep,
    AutomationCondition,
    AutomationExecutionLog,
    AutomationScheduledJob,
    AutomationTrigger,
    AutomationWebhookEndpoint,
    AutomationWorkflow,
)
from app.apps.automation.schemas import (
    ApprovalDecision,
    ApprovalRequestCreate,
    ApprovalRuleCreate,
    AssignmentRuleCreate,
    BlueprintCreate,
    BlueprintTransitionValidate,
    CadenceCreate,
    CadenceEnrollRequest,
    RuleTestRequest,
    WebhookCreate,
    WebhookTestRequest,
    WorkflowCreate,
    WorkflowTestRequest,
    WorkflowUpdate,
)
from app.apps.automation.services.engine import (
    evaluate_conditions,
    execute_workflow,
    organization_id_for,
    retry_execution_log,
    serialize_log,
    validate_action_schema,
    validate_condition_schema,
    validate_workflow_payload,
)
from app.core.deps import RequirePermission, get_db
from app.models.notification import Notification
from app.models.user import User


router = APIRouter(prefix="/automation", tags=["Automation Studio"])


def _serialize(item) -> dict[str, Any] | None:
    if item is None:
        return None
    data: dict[str, Any] = {}
    for column in item.__table__.columns:
        value = getattr(item, column.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column.name] = value
    return data


def _workflow_payload(db: Session, workflow: AutomationWorkflow) -> dict[str, Any]:
    data = _serialize(workflow) or {}
    condition_rows = db.query(AutomationCondition).filter(AutomationCondition.workflow_id == workflow.id).order_by(AutomationCondition.order_index).all()
    action_rows = db.query(AutomationAction).filter(AutomationAction.workflow_id == workflow.id).order_by(AutomationAction.order_index).all()
    data["active"] = workflow.is_active
    data["condition_json"] = [item.condition_json for item in condition_rows]
    data["action_json"] = [item.action_json for item in action_rows]
    data["conditions"] = [_serialize(item) for item in condition_rows]
    data["actions"] = [_serialize(item) for item in action_rows]
    return data


def _replace_workflow_parts(db: Session, workflow_id: int, conditions: list[dict[str, Any]], actions: list[dict[str, Any]]) -> None:
    db.query(AutomationCondition).filter(AutomationCondition.workflow_id == workflow_id).delete()
    db.query(AutomationAction).filter(AutomationAction.workflow_id == workflow_id).delete()
    for index, condition in enumerate(conditions):
        validate_condition_schema(condition)
        db.add(AutomationCondition(workflow_id=workflow_id, condition_json=condition, order_index=index))
    for index, action in enumerate(actions):
        action_type = validate_action_schema(action)
        db.add(AutomationAction(workflow_id=workflow_id, action_type=action_type, action_json=action, order_index=index))


@router.get("/module-info")
def module_info(current_user: User = Depends(RequirePermission("automation_view", "automation_manage"))):
    return {
        "module": "automation",
        "title": "Automation Studio",
        "permissions": [
            "automation_view",
            "automation_manage",
            "automation_execute",
            "automation_logs_view",
            "automation_approval_view",
            "automation_approval_manage",
            "automation_approval_decide",
            "automation_webhook_manage",
        ],
    }


@router.get("/workflows")
def list_workflows(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_view", "automation_manage"))):
    items = db.query(AutomationWorkflow).order_by(AutomationWorkflow.created_at.desc()).all()
    return {"items": [_workflow_payload(db, item) for item in items], "total": len(items)}


@router.post("/workflows", status_code=201)
def create_workflow(data: WorkflowCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    validate_workflow_payload(data.conditions, data.actions)
    workflow = AutomationWorkflow(
        organization_id=organization_id_for(current_user),
        name=data.name,
        description=data.description,
        module_name=data.module_name,
        record_type=data.record_type,
        trigger_type=data.trigger_type,
        is_active=data.is_active,
        max_execution_depth=data.max_execution_depth,
        created_by=current_user.id,
    )
    db.add(workflow)
    db.flush()
    db.add(AutomationTrigger(workflow_id=workflow.id, trigger_type=data.trigger_type, config_json={"module": data.module_name, "record_type": data.record_type}, is_active=True))
    _replace_workflow_parts(db, workflow.id, data.conditions, data.actions)
    db.commit()
    db.refresh(workflow)
    return _workflow_payload(db, workflow)


@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_view", "automation_manage"))):
    workflow = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _workflow_payload(db, workflow)


@router.put("/workflows/{workflow_id}")
def update_workflow(workflow_id: int, data: WorkflowUpdate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    workflow = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    update_data = data.model_dump(exclude_unset=True, exclude={"conditions", "actions"})
    for key, value in update_data.items():
        setattr(workflow, key, value)
    workflow.updated_by = current_user.id
    if data.conditions is not None or data.actions is not None:
        current_conditions = [item.condition_json for item in db.query(AutomationCondition).filter(AutomationCondition.workflow_id == workflow_id).order_by(AutomationCondition.order_index).all()]
        current_actions = [item.action_json for item in db.query(AutomationAction).filter(AutomationAction.workflow_id == workflow_id).order_by(AutomationAction.order_index).all()]
        _replace_workflow_parts(db, workflow_id, data.conditions if data.conditions is not None else current_conditions, data.actions if data.actions is not None else current_actions)
    db.commit()
    db.refresh(workflow)
    return _workflow_payload(db, workflow)


@router.delete("/workflows/{workflow_id}", status_code=204)
def delete_workflow(workflow_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    workflow = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    db.delete(workflow)
    db.commit()
    return None


@router.post("/workflows/{workflow_id}/activate")
def activate_workflow(workflow_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    workflow = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.is_active = True
    db.commit()
    return _workflow_payload(db, workflow)


@router.post("/workflows/{workflow_id}/deactivate")
def deactivate_workflow(workflow_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    workflow = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    workflow.is_active = False
    db.commit()
    return _workflow_payload(db, workflow)


@router.post("/workflows/{workflow_id}/test")
def test_workflow(workflow_id: int, data: WorkflowTestRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_execute", "automation_manage"))):
    workflow = db.query(AutomationWorkflow).filter(AutomationWorkflow.id == workflow_id).first()
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    context = data.model_dump()
    context["module_name"] = context.get("module_name") or workflow.module_name
    context["record_type"] = context.get("record_type") or workflow.record_type
    context["trigger_type"] = context.get("trigger_type") or workflow.trigger_type
    log = execute_workflow(db, workflow, context, current_user)
    db.commit()
    db.refresh(log)
    return serialize_log(log)


@router.get("/logs")
def list_logs(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_logs_view", "automation_manage"))):
    items = db.query(AutomationExecutionLog).order_by(AutomationExecutionLog.created_at.desc()).limit(200).all()
    return {"items": [serialize_log(item) for item in items], "total": len(items)}


@router.get("/logs/{log_id}")
def get_log(log_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_logs_view", "automation_manage"))):
    log = db.query(AutomationExecutionLog).filter(AutomationExecutionLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Execution log not found")
    return serialize_log(log)


@router.post("/logs/{log_id}/retry")
def retry_log(log_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_execute", "automation_manage"))):
    log = db.query(AutomationExecutionLog).filter(AutomationExecutionLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Execution log not found")
    retry = retry_execution_log(db, log, current_user)
    db.commit()
    db.refresh(retry)
    return serialize_log(retry)


@router.get("/blueprints")
def list_blueprints(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_view", "automation_manage"))):
    items = db.query(AutomationBlueprint).order_by(AutomationBlueprint.created_at.desc()).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


def _blueprint_payload(db: Session, blueprint: AutomationBlueprint) -> dict[str, Any]:
    data = _serialize(blueprint) or {}
    data["stages"] = [_serialize(item) for item in db.query(AutomationBlueprintStage).filter(AutomationBlueprintStage.blueprint_id == blueprint.id).order_by(AutomationBlueprintStage.order_index).all()]
    data["transitions"] = [_serialize(item) for item in db.query(AutomationBlueprintTransition).filter(AutomationBlueprintTransition.blueprint_id == blueprint.id).all()]
    return data


@router.post("/blueprints", status_code=201)
def create_blueprint(data: BlueprintCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    blueprint = AutomationBlueprint(organization_id=organization_id_for(current_user), name=data.name, module_name=data.module_name, record_type=data.record_type, is_active=data.is_active, created_by=current_user.id)
    db.add(blueprint)
    db.flush()
    for index, stage in enumerate(data.stages):
        db.add(AutomationBlueprintStage(
            blueprint_id=blueprint.id,
            stage_key=stage["stage_key"],
            label=stage.get("label") or stage["stage_key"],
            order_index=stage.get("order_index", index),
            required_fields_json=stage.get("required_fields_json") or stage.get("required_fields") or [],
            requires_approval=bool(stage.get("requires_approval", False)),
        ))
    for transition in data.transitions:
        db.add(AutomationBlueprintTransition(
            blueprint_id=blueprint.id,
            from_stage_key=transition["from_stage_key"],
            to_stage_key=transition["to_stage_key"],
            required_fields_json=transition.get("required_fields_json") or transition.get("required_fields") or [],
            requires_approval=bool(transition.get("requires_approval", False)),
            automation_workflow_id=transition.get("automation_workflow_id"),
        ))
    db.commit()
    return _blueprint_payload(db, blueprint)


@router.get("/blueprints/{blueprint_id}")
def get_blueprint(blueprint_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_view", "automation_manage"))):
    blueprint = db.query(AutomationBlueprint).filter(AutomationBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    return _blueprint_payload(db, blueprint)


@router.put("/blueprints/{blueprint_id}")
def update_blueprint(blueprint_id: int, data: BlueprintCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    blueprint = db.query(AutomationBlueprint).filter(AutomationBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    blueprint.name = data.name
    blueprint.module_name = data.module_name
    blueprint.record_type = data.record_type
    blueprint.is_active = data.is_active
    db.commit()
    return _blueprint_payload(db, blueprint)


@router.post("/blueprints/{blueprint_id}/stages", status_code=201)
def add_blueprint_stage(blueprint_id: int, stage: dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    blueprint = db.query(AutomationBlueprint).filter(AutomationBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    item = AutomationBlueprintStage(
        blueprint_id=blueprint_id,
        stage_key=stage["stage_key"],
        label=stage.get("label") or stage["stage_key"],
        order_index=stage.get("order_index", 0),
        required_fields_json=stage.get("required_fields_json") or stage.get("required_fields") or [],
        requires_approval=bool(stage.get("requires_approval", False)),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/blueprints/{blueprint_id}/transitions", status_code=201)
def add_blueprint_transition(blueprint_id: int, transition: dict[str, Any], db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    blueprint = db.query(AutomationBlueprint).filter(AutomationBlueprint.id == blueprint_id).first()
    if not blueprint:
        raise HTTPException(status_code=404, detail="Blueprint not found")
    item = AutomationBlueprintTransition(
        blueprint_id=blueprint_id,
        from_stage_key=transition["from_stage_key"],
        to_stage_key=transition["to_stage_key"],
        required_fields_json=transition.get("required_fields_json") or transition.get("required_fields") or [],
        requires_approval=bool(transition.get("requires_approval", False)),
        automation_workflow_id=transition.get("automation_workflow_id"),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize(item)


@router.post("/blueprints/{blueprint_id}/validate-transition")
def validate_transition(blueprint_id: int, data: BlueprintTransitionValidate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_execute", "automation_manage"))):
    transition = db.query(AutomationBlueprintTransition).filter(
        AutomationBlueprintTransition.blueprint_id == blueprint_id,
        AutomationBlueprintTransition.from_stage_key == data.from_stage_key,
        AutomationBlueprintTransition.to_stage_key == data.to_stage_key,
    ).first()
    if not transition:
        raise HTTPException(status_code=400, detail="Transition is not allowed by blueprint")
    missing = [field for field in (transition.required_fields_json or []) if data.record.get(field) in (None, "")]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {', '.join(missing)}")
    return {"allowed": True, "requires_approval": transition.requires_approval, "transition": _serialize(transition)}


@router.get("/approvals")
def list_approvals(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_view", "automation_approval_manage", "automation_approval_decide"))):
    items = db.query(AutomationApprovalRequest).order_by(AutomationApprovalRequest.created_at.desc()).limit(200).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@router.post("/approvals/rules", status_code=201)
def create_approval_rule(data: ApprovalRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_manage", "automation_manage"))):
    rule = AutomationApprovalRule(organization_id=organization_id_for(current_user), name=data.name, module_name=data.module_name, record_type=data.record_type, condition_json=data.condition_json, is_active=data.is_active, created_by=current_user.id)
    db.add(rule)
    db.flush()
    for index, step in enumerate(data.steps or [{"approver_role": "manager"}]):
        db.add(AutomationApprovalStep(rule_id=rule.id, step_order=step.get("step_order", index + 1), approver_role=step.get("approver_role"), approver_user_id=step.get("approver_user_id"), escalation_hours=step.get("escalation_hours")))
    db.commit()
    return _serialize(rule)


@router.post("/approvals", status_code=201)
def create_approval_request(data: ApprovalRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_manage", "automation_execute"))):
    request = AutomationApprovalRequest(organization_id=organization_id_for(current_user), rule_id=data.rule_id, module_name=data.module_name, record_type=data.record_type, record_id=data.record_id, status="draft", submitted_by=current_user.id, payload_json=data.payload_json or {}, history_json=[])
    db.add(request)
    db.commit()
    db.refresh(request)
    return _serialize(request)


@router.post("/approvals/{request_id}/submit")
def submit_approval(request_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_manage", "automation_execute"))):
    request = db.query(AutomationApprovalRequest).filter(AutomationApprovalRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=400, detail="Only draft or rejected approvals can be submitted")
    request.status = "pending"
    request.history_json = (request.history_json or []) + [{"status": "pending", "by": current_user.id, "at": datetime.now(timezone.utc).isoformat()}]
    db.commit()
    return _serialize(request)


@router.post("/approvals/{request_id}/approve")
def approve_request(request_id: int, data: ApprovalDecision, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_decide"))):
    request = db.query(AutomationApprovalRequest).filter(AutomationApprovalRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending approvals can be approved")
    request.status = "approved"
    request.decided_by = current_user.id
    request.decision_comment = data.comment
    request.history_json = (request.history_json or []) + [{"status": "approved", "by": current_user.id, "comment": data.comment, "at": datetime.now(timezone.utc).isoformat()}]
    db.commit()
    return _serialize(request)


@router.post("/approval-requests/{request_id}/approve")
def approve_approval_request_alias(request_id: int, data: ApprovalDecision, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_decide"))):
    return approve_request(request_id, data, db, current_user)


@router.post("/approvals/{request_id}/reject")
def reject_request(request_id: int, data: ApprovalDecision, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_decide"))):
    request = db.query(AutomationApprovalRequest).filter(AutomationApprovalRequest.id == request_id).first()
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending approvals can be rejected")
    request.status = "rejected"
    request.decided_by = current_user.id
    request.decision_comment = data.comment
    request.history_json = (request.history_json or []) + [{"status": "rejected", "by": current_user.id, "comment": data.comment, "at": datetime.now(timezone.utc).isoformat()}]
    db.commit()
    return _serialize(request)


@router.post("/approval-requests/{request_id}/reject")
def reject_approval_request_alias(request_id: int, data: ApprovalDecision, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_approval_decide"))):
    return reject_request(request_id, data, db, current_user)


@router.get("/assignment-rules")
def list_assignment_rules(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_view", "automation_manage"))):
    items = db.query(AutomationAssignmentRule).order_by(AutomationAssignmentRule.created_at.desc()).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@router.post("/assignment-rules", status_code=201)
def create_assignment_rule(data: AssignmentRuleCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    conditions = data.condition_json if isinstance(data.condition_json, list) else ([data.condition_json] if data.condition_json else [])
    for condition in conditions:
        validate_condition_schema(condition)
    rule = AutomationAssignmentRule(organization_id=organization_id_for(current_user), name=data.name, module_name=data.module_name, record_type=data.record_type, condition_json=data.condition_json, assignment_json=data.assignment_json, is_active=data.is_active, created_by=current_user.id)
    db.add(rule)
    db.commit()
    return _serialize(rule)


@router.post("/assignment-rules/{rule_id}/test")
def test_assignment_rule(rule_id: int, data: RuleTestRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_execute", "automation_manage"))):
    rule = db.query(AutomationAssignmentRule).filter(AutomationAssignmentRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Assignment rule not found")
    conditions = rule.condition_json if isinstance(rule.condition_json, list) else ([rule.condition_json] if rule.condition_json else [])
    matched = evaluate_conditions(conditions, data.record)
    return {"matched": matched, "assignment": rule.assignment_json if matched else None}


@router.get("/cadences")
def list_cadences(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_view", "automation_manage"))):
    items = db.query(AutomationCadence).order_by(AutomationCadence.created_at.desc()).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@router.post("/cadences", status_code=201)
def create_cadence(data: CadenceCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    cadence = AutomationCadence(organization_id=organization_id_for(current_user), name=data.name, module_name=data.module_name, target_type=data.target_type, stop_rules_json=data.stop_rules_json, status=data.status, created_by=current_user.id)
    db.add(cadence)
    db.flush()
    for index, step in enumerate(data.steps):
        if step.get("step_type") not in {"task", "email", "whatsapp_placeholder", "sms_placeholder"}:
            raise HTTPException(status_code=400, detail="Unsupported cadence step type")
        db.add(AutomationCadenceStep(cadence_id=cadence.id, step_order=step.get("step_order", index + 1), step_type=step["step_type"], delay_hours=step.get("delay_hours", 0), payload_json=step.get("payload_json") or step))
    db.commit()
    return _serialize(cadence)


@router.post("/cadences/{cadence_id}/enroll")
def enroll_cadence(cadence_id: int, data: CadenceEnrollRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_execute", "automation_manage"))):
    cadence = db.query(AutomationCadence).filter(AutomationCadence.id == cadence_id).first()
    if not cadence:
        raise HTTPException(status_code=404, detail="Cadence not found")
    job = AutomationScheduledJob(organization_id=organization_id_for(current_user), job_type="cadence", module_name=cadence.module_name, record_type=data.record_type, record_id=data.record_id, status="scheduled", payload_json={"cadence_id": cadence_id, "payload": data.payload_json or {}}, created_by=current_user.id)
    db.add(job)
    db.commit()
    return _serialize(job)


@router.post("/cadences/{cadence_id}/pause")
def pause_cadence(cadence_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    cadence = db.query(AutomationCadence).filter(AutomationCadence.id == cadence_id).first()
    if not cadence:
        raise HTTPException(status_code=404, detail="Cadence not found")
    cadence.status = "paused"
    db.commit()
    return _serialize(cadence)


@router.post("/cadences/{cadence_id}/resume")
def resume_cadence(cadence_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    cadence = db.query(AutomationCadence).filter(AutomationCadence.id == cadence_id).first()
    if not cadence:
        raise HTTPException(status_code=404, detail="Cadence not found")
    cadence.status = "active"
    db.commit()
    return _serialize(cadence)


@router.post("/cadences/{cadence_id}/complete")
def complete_cadence(cadence_id: int, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_manage"))):
    cadence = db.query(AutomationCadence).filter(AutomationCadence.id == cadence_id).first()
    if not cadence:
        raise HTTPException(status_code=404, detail="Cadence not found")
    cadence.status = "completed"
    db.commit()
    return _serialize(cadence)


@router.get("/webhooks")
def list_webhooks(db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_view", "automation_webhook_manage"))):
    items = db.query(AutomationWebhookEndpoint).order_by(AutomationWebhookEndpoint.created_at.desc()).all()
    return {"items": [_serialize(item) for item in items], "total": len(items)}


@router.post("/webhooks", status_code=201)
def create_webhook(data: WebhookCreate, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_webhook_manage"))):
    if not (data.target_url.startswith("https://") or data.target_url.startswith("http://localhost") or data.target_url.startswith("http://127.0.0.1")):
        raise HTTPException(status_code=400, detail="Webhook endpoints must use HTTPS outside local development")
    endpoint = AutomationWebhookEndpoint(organization_id=organization_id_for(current_user), name=data.name, target_url=data.target_url, event_types_json=data.event_types_json, secret_ref=data.secret_ref, is_active=data.is_active, created_by=current_user.id)
    db.add(endpoint)
    db.commit()
    return _serialize(endpoint)


@router.post("/webhooks/{webhook_id}/test")
def test_webhook(webhook_id: int, data: WebhookTestRequest, db: Session = Depends(get_db), current_user: User = Depends(RequirePermission("automation_webhook_manage"))):
    endpoint = db.query(AutomationWebhookEndpoint).filter(AutomationWebhookEndpoint.id == webhook_id).first()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")
    log = AutomationExecutionLog(organization_id=organization_id_for(current_user), workflow_id=None, module_name="automation", record_type="webhook", record_id=endpoint.id, trigger_type="webhook_test", status="success", request_json={"payload": data.payload, "endpoint_id": endpoint.id}, result_json={"delivery": "logged_only", "target_url": endpoint.target_url}, created_by=current_user.id)
    db.add(log)
    db.commit()
    return serialize_log(log)
