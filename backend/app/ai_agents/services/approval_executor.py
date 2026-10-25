from __future__ import annotations
from app.access.catalog import permission_objects

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai_agents.adapters.crm_ai_adapter import CrmAiAdapter
from app.ai_agents.adapters.hrms_ai_adapter import HrmsAiAdapter
from app.ai_agents.adapters.pms_ai_adapter import PmsAiAdapter
from app.ai_agents.models import AiActionApproval
from app.ai_agents.services.advanced_security import AiAgentPermissionService, AiUsageService
from app.ai_agents.services.audit import AiAuditService
from app.models.user import User


@dataclass(frozen=True)
class ApprovalActionDefinition:
    module: str
    permission: str
    executor_name: str
    required_fields: tuple[str, ...]
    aliases: tuple[str, ...] = ()


ACTION_DEFINITIONS: dict[str, ApprovalActionDefinition] = {
    "EXECUTE_PMS_OPERATOR_SETUP": ApprovalActionDefinition(
        module="PMS", permission="pms_manage_tasks", executor_name="operator.execute_setup",
        required_fields=("proposal_id", "plan_hash"),
    ),
    "EXECUTE_PMS_OPERATOR_PLAN": ApprovalActionDefinition(
        module="PMS", permission="pms_manage_tasks", executor_name="operator.execute_run",
        required_fields=("run_id", "plan_hash"),
    ),
    "CREATE_CRM_FOLLOWUP_TASK": ApprovalActionDefinition(
        module="CRM",
        permission="crm_manage",
        executor_name="crm.execute_create_followup_task",
        required_fields=("related_entity_type", "related_entity_id", "title", "description", "due_date", "priority"),
        aliases=("crm.create_followup_task", "crm_create_followup_task_draft"),
    ),
    "UPDATE_CRM_LEAD_SCORE_STATUS": ApprovalActionDefinition(
        module="CRM",
        permission="crm_manage",
        executor_name="crm.execute_lead_score_status_update",
        required_fields=("lead_id", "reason"),
        aliases=("crm.update_lead", "crm_propose_lead_update"),
    ),
    "CREATE_CRM_DRAFT_MESSAGE": ApprovalActionDefinition(
        module="CRM",
        permission="crm_manage",
        executor_name="crm.execute_create_draft_message",
        required_fields=("related_entity_type", "related_entity_id", "message_type"),
        aliases=("crm.create_draft_message", "crm_draft_message"),
    ),
    "CREATE_PMS_TASK": ApprovalActionDefinition(
        module="PMS",
        permission="pms_manage_tasks",
        executor_name="pms.execute_create_task",
        required_fields=("project_id", "title", "description"),
        aliases=("pms.create_task", "pms_create_task_draft"),
    ),
    "CREATE_PMS_SUBTASK": ApprovalActionDefinition(
        module="PMS",
        permission="pms_manage_tasks",
        executor_name="pms.execute_create_subtask",
        required_fields=("parent_task_id", "title", "description"),
        aliases=("pms.create_subtask", "pms_create_subtask_draft"),
    ),
    "CREATE_PMS_RISK_LOG": ApprovalActionDefinition(
        module="PMS",
        permission="pms_manage_tasks",
        executor_name="pms.execute_create_risk_log",
        required_fields=("project_id", "risk_title", "risk_description", "severity", "mitigation_plan"),
        aliases=("pms.create_risk_log", "pms_create_risk_log_proposal"),
    ),
    "CREATE_HRMS_LEAVE_REQUEST": ApprovalActionDefinition(
        module="HRMS",
        permission="leave_apply",
        executor_name="hrms.execute_create_leave_request",
        required_fields=("employee_id", "leave_type", "from_date", "to_date", "reason"),
        aliases=("hrms.create_leave_request", "hrms_create_leave_request_proposal"),
    ),
    "CREATE_HRMS_ATTENDANCE_ALERT": ApprovalActionDefinition(
        module="HRMS",
        permission="attendance_manage",
        executor_name="hrms.execute_create_attendance_alert",
        required_fields=("employee_id", "alert_type", "details", "recommended_action"),
        aliases=("hrms.create_attendance_alert", "hrms_create_attendance_alert_proposal"),
    ),
    "CREATE_HRMS_LETTER_DRAFT": ApprovalActionDefinition(
        module="HRMS",
        permission="employee_update",
        executor_name="hrms.execute_create_letter_draft",
        required_fields=("employee_id", "letter_type"),
        aliases=("hrms.issue_letter", "hrms_generate_letter_draft"),
    ),
    "SAVE_CANDIDATE_SCREENING_SUMMARY": ApprovalActionDefinition(
        module="HRMS",
        permission="recruitment_manage",
        executor_name="hrms.execute_save_candidate_screening_summary",
        required_fields=("candidate_id", "summary"),
        aliases=("hrms.save_candidate_screening_summary",),
    ),
}

UNSUPPORTED_ACTIONS = {
    "DELETE_RECORD",
    "SEND_EXTERNAL_MESSAGE",
    "APPROVE_LEAVE",
    "REJECT_LEAVE",
    "CHANGE_SALARY",
    "MODIFY_ATTENDANCE",
    "TERMINATE_EMPLOYEE",
    "ISSUE_FINAL_WARNING_LETTER",
    "CLOSE_DEAL",
    "CHANGE_PROJECT_DEADLINE",
    "REASSIGN_PROJECT_OWNER",
    "CHANGE_FINANCIAL_RECORD",
}


class AiApprovalExecutorService:
    def __init__(self, db: Session):
        self.db = db
        self.audit = AiAuditService(db)

    def execute_approved_action(
        self,
        *,
        user: User,
        approval_id: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AiActionApproval:
        approval = self.db.query(AiActionApproval).filter(AiActionApproval.id == approval_id).with_for_update().first()
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.action_type == "EXECUTE_PMS_OPERATOR_PLAN":
            from app.ai_operator.models import OperatorRun
            run_id = (approval.proposed_action_json or {}).get("input", {}).get("run_id")
            operator_run = self.db.get(OperatorRun, run_id)
            if operator_run and operator_run.background:
                from app.ai_operator.jobs import queue_approved_plan
                return queue_approved_plan(self.db, user, approval)
        if approval.execution_status == "executed":
            approval.execution_result_json = approval.execution_result_json or {"success": True, "message": "This approval was already executed."}
            return approval
        if approval.status != "pending":
            raise HTTPException(status_code=400, detail="Approval is not pending")
        self._ensure_can_approve(user, approval)
        if not AiAgentPermissionService(self.db).can_approve_agent_action(user, approval.id):
            raise HTTPException(status_code=403, detail="You do not have permission to approve this AI action")
        approval.execution_status = "executing"
        self.db.flush()

        try:
            action_key, definition = self._resolve_action(approval)
            proposed_action = self._proposed_action(approval)
            self._validate_proposed_action(definition, proposed_action)
            if not self._has_permission(user, definition.permission):
                self._audit(
                    approval,
                    user,
                    "AI_APPROVAL_PERMISSION_DENIED",
                    {"approval_id": approval.id, "required_permission": definition.permission},
                    {"success": False, "error_code": "PERMISSION_DENIED"},
                    "failed",
                    ip_address,
                    user_agent,
                )
                raise HTTPException(status_code=403, detail="You do not have permission to execute this AI proposed action.")

            result = self._dispatch(definition, user, proposed_action)
            if isinstance(result, dict) and result.get("success") is False:
                return self._mark_failed(
                    approval,
                    user,
                    str(result.get("error_code") or "APPROVAL_EXECUTION_FAILED"),
                    str(result.get("message") or "Approved action execution failed."),
                    ip_address,
                    user_agent,
                    result,
                )

            now = datetime.utcnow()
            approval.status = "approved"
            approval.execution_status = "executed"
            approval.approved_by = user.id
            approval.approved_at = now
            approval.executed_at = now
            approval.execution_result_json = {"success": True, "action_type": action_key, "result": result}
            approval.updated_at = now
            self.db.flush()
            AiUsageService(self.db).record_event(user=user, agent_id=approval.agent_id, module=approval.module, event_type="approval_executed")
            self._audit(approval, user, "AI_APPROVED_ACTION_EXECUTED", {"approval_id": approval.id}, approval.execution_result_json, "success", ip_address, user_agent)
            return approval
        except HTTPException:
            raise
        except Exception as exc:
            return self._mark_failed(approval, user, "APPROVAL_EXECUTION_FAILED", str(exc), ip_address, user_agent)

    def _ensure_can_approve(self, user: User, approval: AiActionApproval) -> None:
        if user.is_superuser:
            return
        if approval.user_id != user.id:
            self._audit(approval, user, "AI_APPROVAL_PERMISSION_DENIED", {"approval_id": approval.id}, {"reason": "approval owner mismatch"}, "failed", None, None)
            raise HTTPException(status_code=403, detail="You do not have permission to approve this AI action")

    def _resolve_action(self, approval: AiActionApproval) -> tuple[str, ApprovalActionDefinition]:
        candidate_values = {
            str(approval.action_type or ""),
            str((approval.proposed_action_json or {}).get("tool_name") or ""),
        }
        for key, definition in ACTION_DEFINITIONS.items():
            if key in candidate_values or any(alias in candidate_values for alias in definition.aliases):
                if approval.module and approval.module.upper() != definition.module:
                    raise ValueError("Approval module does not match the supported action definition")
                return key, definition
        if str(approval.action_type or "").upper() in UNSUPPORTED_ACTIONS:
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "error_code": "ACTION_NOT_SUPPORTED_IN_FIRST_RELEASE",
                    "message": "This action is not enabled for automatic AI approval execution in the first release.",
                },
            )
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "error_code": "ACTION_NOT_SUPPORTED_IN_FIRST_RELEASE",
                "message": "This action is not enabled for automatic AI approval execution in the first release.",
            },
        )

    def _proposed_action(self, approval: AiActionApproval) -> dict[str, Any]:
        data = approval.proposed_action_json
        if not isinstance(data, dict):
            raise ValueError("Invalid proposed action JSON")
        return data

    def _validate_proposed_action(self, definition: ApprovalActionDefinition, proposed_action: dict[str, Any]) -> None:
        input_data = proposed_action.get("input") if isinstance(proposed_action.get("input"), dict) else proposed_action
        if not isinstance(input_data, dict):
            raise ValueError("Invalid proposed action input")
        dangerous = {"sql", "raw_sql", "query", "password", "api_key", "openai_api_key", "delete", "drop"}
        included_dangerous = dangerous.intersection({str(key).lower() for key in input_data.keys()})
        if included_dangerous:
            raise ValueError(f"Dangerous fields are not allowed in approved AI actions: {', '.join(sorted(included_dangerous))}")
        missing = [field for field in definition.required_fields if input_data.get(field) in (None, "")]
        if missing:
            raise ValueError(f"Missing required proposed action fields: {', '.join(missing)}")

    def _dispatch(self, definition: ApprovalActionDefinition, user: User, proposed_action: dict[str, Any]) -> dict[str, Any]:
        namespace, method_name = definition.executor_name.split(".", 1)
        if namespace == "operator":
            from app.ai_operator.service import OperatorExecutor
            return getattr(OperatorExecutor(self.db), method_name)(user, proposed_action)
        adapters = {
            "crm": CrmAiAdapter(self.db),
            "pms": PmsAiAdapter(self.db),
            "hrms": HrmsAiAdapter(self.db),
        }
        adapter = adapters[namespace]
        method: Callable[[User, dict[str, Any]], dict[str, Any]] | None = getattr(adapter, method_name, None)
        if not method:
            return {
                "success": False,
                "error_code": "SERVICE_METHOD_MISSING",
                "message": "Required existing module service method is not available yet.",
                "missing_method": definition.executor_name,
            }
        return method(user, proposed_action)

    def _mark_failed(
        self,
        approval: AiActionApproval,
        user: User,
        error_code: str,
        message: str,
        ip_address: str | None,
        user_agent: str | None,
        result: dict[str, Any] | None = None,
    ) -> AiActionApproval:
        now = datetime.utcnow()
        approval.status = "failed"
        approval.execution_status = "failed"
        approval.execution_result_json = result or {"success": False, "error_code": error_code, "message": message}
        approval.execution_error = message
        approval.updated_at = now
        self.db.flush()
        self._audit(approval, user, "AI_APPROVED_ACTION_FAILED", {"approval_id": approval.id}, approval.execution_result_json, "failed", ip_address, user_agent)
        return approval

    def _has_permission(self, user: User, permission: str) -> bool:
        if not permission or user.is_superuser:
            return True
        permissions = {item.name for item in (permission_objects(user))}
        if "*" in permissions or permission in permissions:
            return True
        aliases = {
            "crm_manage": {"crm_admin"},
            "pms_manage_tasks": {"pms_manage_projects", "pms_admin"},
            "leave_apply": {"leave_manage"},
            "attendance_manage": {"attendance_view"},
            "employee_update": {"employee_sensitive_view"},
            "recruitment_manage": set(),
        }
        return bool(permissions.intersection(aliases.get(permission, set())))

    def _audit(
        self,
        approval: AiActionApproval,
        user: User,
        action: str,
        input_json: dict[str, Any],
        output_json: dict[str, Any],
        status: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self.audit.log(
            user=user,
            agent_id=approval.agent_id,
            module=approval.module,
            action=action,
            related_entity_type=approval.related_entity_type,
            related_entity_id=approval.related_entity_id,
            input_json=input_json,
            output_json=output_json,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
        )
