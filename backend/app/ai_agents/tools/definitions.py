from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai_agents.tools.tool_schemas import arr, enum, i, obj, s, schema


@dataclass(frozen=True)
class AiToolDefinition:
    tool_name: str
    module: str
    description: str
    input_schema: dict[str, Any]
    allowed_agent_codes: tuple[str, ...]
    required_permission: str
    risk_level: str
    requires_approval: bool
    executor: str
    action_type: str | None = None


CRM_TOOLS = [
    AiToolDefinition("crm_get_lead", "CRM", "Fetch one CRM lead visible to the user.", schema({"lead_id": i()}, ["lead_id"]), ("crm_lead_qualification",), "crm_view", "low", False, "crm.get_lead_by_id"),
    AiToolDefinition("crm_search_duplicate_leads", "CRM", "Find possible duplicate CRM leads.", schema({"lead_id": i(), "email": s(), "mobile": s(), "company_name": s()}), ("crm_lead_qualification",), "crm_view", "low", False, "crm.search_duplicate_leads"),
    AiToolDefinition("crm_get_lead_activities", "CRM", "Fetch activities, notes, and tasks for a CRM lead.", schema({"lead_id": i()}, ["lead_id"]), ("crm_lead_qualification", "crm_followup"), "crm_view", "low", False, "crm.get_lead_activities"),
    AiToolDefinition("crm_get_overdue_followups", "CRM", "Find overdue CRM follow-up tasks.", schema({"from_date": s(), "to_date": s(), "owner_id": i()}), ("crm_followup", "business_summary"), "crm_view", "low", False, "crm.get_overdue_followups"),
    AiToolDefinition("crm_get_deal", "CRM", "Fetch one CRM deal visible to the user.", schema({"deal_id": i()}, ["deal_id"]), ("crm_deal_analyzer",), "crm_view", "low", False, "crm.get_deal_by_id"),
    AiToolDefinition("crm_get_deal_notes", "CRM", "Fetch notes for a CRM deal.", schema({"deal_id": i()}, ["deal_id"]), ("crm_deal_analyzer",), "crm_view", "low", False, "crm.get_deal_notes"),
    AiToolDefinition("crm_get_deal_activities", "CRM", "Fetch activities for a CRM deal.", schema({"deal_id": i()}, ["deal_id"]), ("crm_deal_analyzer",), "crm_view", "low", False, "crm.get_deal_activities"),
    AiToolDefinition("crm_get_customer", "CRM", "Fetch one CRM customer/account.", schema({"customer_id": i()}, ["customer_id"]), ("crm_customer_summary",), "crm_view", "low", False, "crm.get_customer_by_id"),
    AiToolDefinition("crm_get_customer_deals", "CRM", "Fetch deals for a CRM customer/account.", schema({"customer_id": i()}, ["customer_id"]), ("crm_customer_summary",), "crm_view", "low", False, "crm.get_customer_deals"),
    AiToolDefinition("crm_get_customer_activities", "CRM", "Fetch activities for a CRM customer/account.", schema({"customer_id": i()}, ["customer_id"]), ("crm_customer_summary",), "crm_view", "low", False, "crm.get_customer_activities"),
    AiToolDefinition("crm_create_followup_task_draft", "CRM", "Create a proposed CRM follow-up task draft.", schema({"related_entity_type": enum(["lead", "deal", "customer"]), "related_entity_id": i(), "title": s(), "description": s(), "due_date": s(), "priority": enum(["low", "medium", "high"])}, ["related_entity_type", "related_entity_id", "title", "description", "due_date", "priority"]), ("crm_followup", "crm_lead_qualification"), "crm_manage", "medium", True, "crm.create_followup_task_draft", "crm.create_followup_task"),
    AiToolDefinition("crm_propose_lead_update", "CRM", "Create a proposed CRM lead update.", schema({"lead_id": i(), "proposed_status": s(), "proposed_score": i(), "reason": s()}, ["lead_id", "reason"]), ("crm_lead_qualification",), "crm_manage", "medium", True, "crm.propose_lead_update", "crm.update_lead"),
    AiToolDefinition("crm_draft_message", "CRM", "Create a CRM message draft structure without sending.", schema({"related_entity_type": enum(["lead", "deal", "customer"]), "related_entity_id": i(), "message_type": enum(["email", "whatsapp", "sms"]), "purpose": s(), "tone": enum(["professional", "friendly", "firm"]), "key_points": arr()}, ["related_entity_type", "related_entity_id", "message_type", "purpose"]), ("crm_lead_qualification", "crm_followup", "crm_deal_analyzer"), "crm_view", "low", False, "crm.draft_crm_message"),
]

PMS_TOOLS = [
    AiToolDefinition("pms_get_project", "PMS", "Fetch one PMS project visible to the user.", schema({"project_id": i()}, ["project_id"]), ("pms_project_status", "business_summary"), "pms_view", "low", False, "pms.get_project_by_id"),
    AiToolDefinition("pms_get_project_tasks", "PMS", "Fetch tasks for a PMS project.", schema({"project_id": i(), "status": s()}, ["project_id"]), ("pms_project_status", "pms_deadline_risk", "pms_task_planning"), "pms_view", "low", False, "pms.get_project_tasks"),
    AiToolDefinition("pms_get_delayed_tasks", "PMS", "Fetch delayed tasks for a PMS project.", schema({"project_id": i()}, ["project_id"]), ("pms_project_status", "pms_deadline_risk", "business_summary"), "pms_view", "low", False, "pms.get_delayed_tasks"),
    AiToolDefinition("pms_get_milestones", "PMS", "Fetch project milestones.", schema({"project_id": i()}, ["project_id"]), ("pms_project_status", "pms_deadline_risk"), "pms_view", "low", False, "pms.get_milestones"),
    AiToolDefinition("pms_get_project_comments", "PMS", "Fetch project comments.", schema({"project_id": i()}, ["project_id"]), ("pms_project_status", "pms_meeting_notes"), "pms_view", "low", False, "pms.get_project_comments"),
    AiToolDefinition("pms_get_team_members", "PMS", "Fetch project team members.", schema({"project_id": i()}, ["project_id"]), ("pms_task_planning",), "pms_view", "low", False, "pms.get_team_members"),
    AiToolDefinition("pms_get_team_workload", "PMS", "Fetch project workload summary.", schema({"project_id": i()}, ["project_id"]), ("pms_task_planning", "pms_deadline_risk"), "pms_view", "low", False, "pms.get_team_workload"),
    AiToolDefinition("pms_get_task_dependencies", "PMS", "Fetch task dependencies.", schema({"project_id": i(), "task_id": i()}), ("pms_deadline_risk",), "pms_view", "low", False, "pms.get_task_dependencies"),
    AiToolDefinition("pms_create_task_draft", "PMS", "Create a proposed PMS task draft.", schema({"project_id": i(), "title": s(), "description": s(), "assignee_id": i(), "due_date": s(), "priority": enum(["low", "medium", "high"])}, ["project_id", "title", "description"]), ("pms_task_planning", "pms_meeting_notes"), "pms_manage_tasks", "medium", True, "pms.create_task_draft", "pms.create_task"),
    AiToolDefinition("pms_create_subtask_draft", "PMS", "Create a proposed PMS sub-task draft.", schema({"parent_task_id": i(), "title": s(), "description": s(), "assignee_id": i(), "due_date": s()}, ["parent_task_id", "title", "description"]), ("pms_task_planning",), "pms_manage_tasks", "medium", True, "pms.create_subtask_draft", "pms.create_subtask"),
    AiToolDefinition("pms_create_risk_log_proposal", "PMS", "Create a proposed PMS risk log.", schema({"project_id": i(), "risk_title": s(), "risk_description": s(), "severity": enum(["low", "medium", "high", "critical"]), "mitigation_plan": s()}, ["project_id", "risk_title", "risk_description", "severity", "mitigation_plan"]), ("pms_deadline_risk",), "pms_manage_tasks", "medium", True, "pms.create_risk_log_proposal", "pms.create_risk_log"),
    AiToolDefinition("pms_create_project_status_report_draft", "PMS", "Create a project status report draft.", schema({"project_id": i(), "report_type": enum(["daily", "weekly", "monthly", "client", "internal"]), "summary": s(), "risks": arr(), "recommendations": arr()}, ["project_id", "report_type"]), ("pms_project_status",), "pms_view", "low", False, "pms.create_project_status_report_draft"),
]

HRMS_TOOLS = [
    AiToolDefinition("hrms_get_employee", "HRMS", "Fetch one employee visible to the user.", schema({"employee_id": i()}, ["employee_id"]), ("hrms_leave_assistant", "hrms_attendance_anomaly", "hrms_letter_drafting"), "", "low", False, "hrms.get_employee_by_id"),
    AiToolDefinition("hrms_get_leave_balance", "HRMS", "Fetch employee leave balances.", schema({"employee_id": i()}, ["employee_id"]), ("hrms_leave_assistant",), "leave_view", "low", False, "hrms.get_leave_balance"),
    AiToolDefinition("hrms_get_team_leave_calendar", "HRMS", "Fetch team leave calendar context.", schema({"team_id": i(), "manager_id": i(), "from_date": s(), "to_date": s()}), ("hrms_leave_assistant",), "leave_view", "low", False, "hrms.get_team_leave_calendar"),
    AiToolDefinition("hrms_search_policy", "HRMS", "Search published HR policies.", schema({"query": s()}, ["query"]), ("hrms_policy_assistant",), "", "low", False, "hrms.search_policy"),
    AiToolDefinition("hrms_get_policy_document", "HRMS", "Fetch one published HR policy document.", schema({"policy_id": i()}, ["policy_id"]), ("hrms_policy_assistant",), "", "low", False, "hrms.get_policy_document"),
    AiToolDefinition("hrms_get_attendance", "HRMS", "Fetch employee attendance records.", schema({"employee_id": i(), "from_date": s(), "to_date": s()}, ["employee_id", "from_date", "to_date"]), ("hrms_attendance_anomaly",), "attendance_view", "low", False, "hrms.get_attendance"),
    AiToolDefinition("hrms_get_shift", "HRMS", "Fetch employee shift context.", schema({"employee_id": i()}, ["employee_id"]), ("hrms_attendance_anomaly",), "attendance_view", "low", False, "hrms.get_shift"),
    AiToolDefinition("hrms_get_job_opening", "HRMS", "Fetch one recruitment job opening.", schema({"job_id": i()}, ["job_id"]), ("hrms_recruitment_screening",), "recruitment_view", "low", False, "hrms.get_job_opening"),
    AiToolDefinition("hrms_get_candidate", "HRMS", "Fetch one candidate profile.", schema({"candidate_id": i()}, ["candidate_id"]), ("hrms_recruitment_screening",), "recruitment_view", "low", False, "hrms.get_candidate"),
    AiToolDefinition("hrms_get_candidate_resume_text", "HRMS", "Fetch candidate resume parsed text if available.", schema({"candidate_id": i()}, ["candidate_id"]), ("hrms_recruitment_screening",), "recruitment_view", "low", False, "hrms.get_candidate_resume_text"),
    AiToolDefinition("hrms_generate_letter_draft", "HRMS", "Create a proposed HR letter draft.", schema({"employee_id": i(), "letter_type": enum(["offer", "appointment", "experience", "warning", "salary_certificate", "internship", "relieving"]), "extra_details": obj()}, ["employee_id", "letter_type"]), ("hrms_letter_drafting",), "employee_view", "high", True, "hrms.generate_letter_draft", "hrms.issue_letter"),
    AiToolDefinition("hrms_create_leave_request_proposal", "HRMS", "Create a proposed leave request.", schema({"employee_id": i(), "leave_type": s(), "from_date": s(), "to_date": s(), "reason": s()}, ["employee_id", "leave_type", "from_date", "to_date", "reason"]), ("hrms_leave_assistant",), "leave_apply", "medium", True, "hrms.create_leave_request_proposal", "hrms.create_leave_request"),
    AiToolDefinition("hrms_create_attendance_alert_proposal", "HRMS", "Create a proposed attendance alert.", schema({"employee_id": i(), "alert_type": enum(["late_arrival", "missing_punch", "frequent_absence", "unusual_pattern"]), "details": s(), "recommended_action": s()}, ["employee_id", "alert_type", "details", "recommended_action"]), ("hrms_attendance_anomaly",), "attendance_view", "medium", True, "hrms.create_attendance_alert_proposal", "hrms.create_attendance_alert"),
]

CROSS_MODULE_TOOLS = [
    AiToolDefinition("cross_get_business_summary", "CROSS", "Fetch a cross-module business summary.", schema({"from_date": s(), "to_date": s()}), ("business_summary",), "reports_view", "low", False, "cross.get_business_summary"),
    AiToolDefinition("cross_get_pending_approvals", "CROSS", "Fetch pending AI approvals.", schema({"module": enum(["CRM", "HRMS", "PMS", "CROSS"])}), ("business_summary",), "notification_view", "low", False, "cross.get_pending_approvals"),
    AiToolDefinition("cross_safe_search_crm", "CROSS", "Permission-scoped CRM search.", schema({"query": s(), "limit": i()}, ["query"]), ("smart_search",), "crm_view", "low", False, "cross.safe_search_crm"),
    AiToolDefinition("cross_safe_search_pms", "CROSS", "Permission-scoped PMS search.", schema({"query": s(), "limit": i()}, ["query"]), ("smart_search",), "pms_view", "low", False, "cross.safe_search_pms"),
    AiToolDefinition("cross_safe_search_hrms", "CROSS", "Permission-scoped HRMS search.", schema({"query": s(), "limit": i()}, ["query"]), ("smart_search",), "employee_view", "low", False, "cross.safe_search_hrms"),
    AiToolDefinition("cross_get_alerts", "CROSS", "Fetch important cross-module alerts if an existing aggregation service is available.", schema({"module": enum(["CRM", "HRMS", "PMS", "CROSS"]), "severity": enum(["low", "medium", "high", "critical"])}), ("smart_notification", "business_summary"), "notification_view", "low", False, "cross.get_alerts"),
]

ALL_TOOL_DEFINITIONS = CRM_TOOLS + PMS_TOOLS + HRMS_TOOLS + CROSS_MODULE_TOOLS

# Every capability has an explicit backend permission; personal records still require native scope.
from dataclasses import replace
ALL_TOOL_DEFINITIONS = [replace(tool, required_permission=tool.required_permission or "employee_view") for tool in ALL_TOOL_DEFINITIONS]
