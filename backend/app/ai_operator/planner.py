"""Shared planning used by synchronous requests and durable workers."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from app.ai_agents.models import AiActionApproval, AiAgent, AiAgentSetting
from app.ai_agents.services.advanced_security import AiAgentPermissionService, AiDataRedactionService, AiUsageService, company_id_for
from app.ai_agents.services.registry import AiAgentRegistryService
from app.ai_operator.models import OperatorProvider, OperatorRun
from app.ai_operator.providers import generate_json
from app.ai_operator.provider_scope import resolve_provider
from app.ai_operator.schemas import TaskPlan
from app.ai_operator.service import context_for, digest, require_enabled, scope_key, validate_plan


def planning_agent(db, user):
    require_enabled(db, user)
    AiAgentRegistryService(db).ensure_seed_data()
    agent = db.query(AiAgent).filter_by(code="pms_task_planning", is_active=True).first()
    if not agent or not AiAgentPermissionService(db).can_use_agent(user, agent.id):
        raise HTTPException(403, "Task planning agent is unavailable")
    setting = db.query(AiAgentSetting).filter_by(agent_id=agent.id, company_id=company_id_for(user)).first()
    if setting and not setting.is_enabled:
        raise HTTPException(403, "Task planning agent is disabled")
    AiUsageService(db).check_limits(user=user, agent=agent, module="PMS")
    return agent


def generate_plan(db, user, run):
    planning_agent(db, user)
    project, tasks, context = context_for(db, user, run.project_id, run.selection)
    if scope_key(db, user, project.workspace_id) != run.scope_key:
        raise HTTPException(403, "Run scope changed")
    config = resolve_provider(db, user, run.provider, project.workspace_id)
    if not config or not config.enabled or not config.data_sharing_allowed:
        raise HTTPException(409, "Provider unavailable")
    history, parent_id = [], run.parent_run_id
    for _ in range(8):
        if not parent_id:
            break
        parent = db.query(OperatorRun).filter_by(id=parent_id, user_id=user.id, project_id=run.project_id).first()
        if not parent:
            raise HTTPException(403, "Parent context unavailable")
        from app.ai_agents.security import verify
        verify(db,user,parent.security_context,history=True)
        history.append({"command": parent.command, "plan": parent.plan, "committed_result": parent.result})
        parent_id = parent.parent_run_id
    from app.ai_agents.security import bounded_result
    context_for_model=bounded_result(db,user,context)
    outbound = AiDataRedactionService().redact_for_ai(user, "PMS", {"command": run.command, "authorized_context": context_for_model,
        "prior_turns_newest_first": history, "local_time": datetime.now(ZoneInfo(run.timezone)).isoformat(),
        "timezone": run.timezone,
        "instructions": "Revise the previous plan using the follow-up command. Do not repeat committed effects. Keep all targets inside the frozen selection. Step depends_on uses earlier one-based step positions; omitted means preceding steps. Dates must be explicit ISO dates."})
    output = generate_json(db, user, config, prompt=json.dumps(outbound), schema=TaskPlan.model_json_schema(), run_id=run.id, usage_scope=run.scope_key)
    plan = TaskPlan.model_validate(output)
    validate_plan(db, user, run, plan)
    snapshots = {str(task.id): digest(snapshot) for task, snapshot in zip(tasks, context["tasks"])}
    return plan, snapshots


def publish_plan(db, user, run, plan, snapshots):
    agent = planning_agent(db, user)
    run.snapshots = snapshots
    run.plan = plan.model_dump(mode="json", exclude_none=True)
    run.plan_hash = digest(run.plan)
    run.error_code = None
    if plan.clarification:
        run.status = "needs_clarification"
    else:
        approval = AiActionApproval(user_id=user.id, agent_id=agent.id, module="PMS", action_type="EXECUTE_PMS_OPERATOR_PLAN",
            related_entity_type="operator_run", related_entity_id=str(run.id),
            proposed_action_json={"input": {"run_id": run.id, "plan_hash": run.plan_hash}, "preview": run.plan,
                                  "task_ids": run.selection, "execution_mode": run.execution_mode},
            status="pending", execution_status="pending", idempotency_key=f"operator:{run.id}:{run.plan_hash}")
        db.add(approval)
        db.flush()
        run.approval_id = approval.id
        run.status = "awaiting_approval"
    AiUsageService(db).record_event(user=user, agent_id=agent.id, module="PMS", event_type="operator_planned")
    from app.ai_agents.services.audit import AiAuditService
    AiAuditService(db).log(user=user, agent_id=agent.id, module="PMS", action="operator.background.plan",
        input_json={"run_id": run.id, "revision": run.revision}, output_json={"status": run.status, "plan_hash": run.plan_hash}, status="success")
