"""Explicit API allowlist. No model-supplied URLs, HTTP methods or tenant IDs."""
from dataclasses import dataclass
from importlib import import_module
from typing import Any
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class CRMTaskInput(Strict):
    title: str = Field(min_length=1, max_length=220)
    description: str | None = None
    priority: str = 'Medium'
    status: str = 'To Do'
    due_date: str | None = None
    lead_id: int | None = None
    contact_id: int | None = None
    company_id: int | None = None
    deal_id: int | None = None


class CRMTaskUpdate(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=220)
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    due_date: str | None = None


@dataclass(frozen=True)
class Tool:
    module: str
    method: str
    path: str
    description: str
    permissions: tuple[str, ...] = ()
    fields: tuple[str, ...] = ()
    model: str | None = None
    guard: str | None = None
    project_target: bool = False
    optional_project: bool = False


TOOLS = {
    'hrms.directory': Tool('HRMS', 'GET', '/employees/directory', 'Find directory names, roles and departments; no payroll or bank details.', fields=('search', 'page', 'per_page')),
    'hrms.my_leave': Tool('HRMS', 'GET', '/leave/my-requests', 'List your own leave requests.', fields=('status', 'page', 'per_page')),
    'hrms.leave_balance': Tool('HRMS', 'GET', '/leave/balance', 'Read your own leave balance.', fields=('year',)),
    'hrms.leave_types': Tool('HRMS', 'GET', '/leave/types', 'List configured leave types.'),
    'hrms.request_leave': Tool('HRMS', 'POST', '/leave/apply', 'Submit your own leave request; manager approval remains separate.',
        fields=('leave_type_id', 'from_date', 'to_date', 'is_half_day', 'half_day_period', 'reason', 'handover_employee_id'), model='app.schemas.leave:LeaveRequestCreate'),
    'hrms.create_ticket': Tool('HRMS', 'POST', '/helpdesk/tickets/json', 'Create your own HR helpdesk ticket.',
        fields=('subject', 'description', 'category_id', 'priority'), model='app.schemas.helpdesk:HelpdeskTicketCreate'),
    'crm.leads': Tool('CRM', 'GET', '/crm/leads', 'Read visible leads.', fields=('search', 'page', 'per_page')),
    'crm.deals': Tool('CRM', 'GET', '/crm/deals', 'Read visible deals.', fields=('search', 'page', 'per_page')),
    'crm.tasks': Tool('CRM', 'GET', '/crm/tasks', 'Read visible CRM tasks.', fields=('search', 'page', 'per_page')),
    'crm.create_task': Tool('CRM', 'POST', '/crm/tasks', 'Create a CRM follow-up task; no outgoing message.', ('crm_activities_manage', 'crm_manage', 'crm_admin'),
        tuple(CRMTaskInput.model_fields), 'app.ai_operator.suite_tools:CRMTaskInput'),
    'crm.update_task': Tool('CRM', 'PATCH', '/crm/tasks/{record_id}', 'Update a visible CRM task.', ('crm_activities_manage', 'crm_manage', 'crm_admin'),
        tuple(CRMTaskUpdate.model_fields), 'app.ai_operator.suite_tools:CRMTaskUpdate', '/crm/tasks/{record_id}'),
    'srm.dashboard': Tool('SRM', 'GET', '/srm/dashboard', 'Read authorized sales and inventory totals.'),
    'srm.invoices': Tool('SRM', 'GET', '/srm/invoices', 'Read authorized invoices and balances.', fields=('page', 'per_page')),
    'srm.inventory': Tool('SRM', 'GET', '/srm/inventory/items', 'Read authorized stock items.', fields=('search', 'page', 'per_page')),
    'srm.draft_invoice': Tool('SRM', 'POST', '/srm/invoices/manual', 'Create a draft invoice only. Issuance, delivery and payment remain separate.', ('srm_invoice_create', 'srm_admin'),
        ('customer_id', 'seller_id', 'contact_id', 'currency', 'issue_date', 'due_date', 'lines'), 'app.apps.srm.schemas:SRMManualInvoiceCreate'),
    'fam.dashboard': Tool('FAM', 'GET', '/fam/dashboard', 'Read company accounting totals; not a bank transfer.'),
    'fam.cost_centers': Tool('FAM', 'GET', '/fam/cost-centers', 'Read authorized accounting cost centers.'),
    'fam.vouchers': Tool('FAM', 'GET', '/fam/vouchers', 'Read authorized vouchers.', fields=('page', 'per_page', 'status')),
    'fam.ledgers': Tool('FAM', 'GET', '/fam/ledgers', 'Read authorized ledger names and IDs.'),
    'fam.voucher_types': Tool('FAM', 'GET', '/fam/voucher-types', 'Read available voucher types.'),
    'fam.create_cost_center': Tool('FAM', 'POST', '/fam/cost-centers', 'Create an accounting cost center.', ('fam_admin', 'fam_cost_center_manage'),
        ('code', 'name', 'parent_id', 'active'), 'app.apps.fam.schemas:CostCenterPayload'),
    'fam.draft_voucher': Tool('FAM', 'POST', '/fam/vouchers', 'Create a draft balanced voucher; posting is a separate finance approval.', ('fam_admin', 'fam_vouchers_create'),
        ('financial_year_id', 'accounting_period_id', 'branch_id', 'voucher_type_id', 'voucher_date', 'reference_number', 'reference_date', 'narration', 'lines'), 'app.apps.fam.schemas:VoucherPayload'),
    'pms.projects': Tool('PMS', 'GET', '/project-management/projects', 'Read accessible PMS projects.'),
    'pms.tasks': Tool('PMS', 'GET', '/project-management/projects/{record_id}/tasks', 'Read tasks in a selected authorized project.'),
    'pms.create_project': Tool('PMS', 'POST', '/project-management/projects', 'Create a project in the selected workspace.', ('pms_manage_projects', 'pms_admin'),
        ('name', 'project_key', 'description', 'priority', 'start_date', 'due_date'), 'app.apps.project_management.schemas:PMSProjectCreate'),
    'pms.create_task': Tool('PMS', 'POST', '/project-management/projects/{record_id}/tasks', 'Create a task in an authorized project.', ('pms_manage_tasks', 'pms_admin'),
        ('title', 'task_key', 'description', 'priority', 'estimated_hours', 'start_date', 'due_date'), 'app.apps.project_management.schemas:PMSTaskCreate', '/project-management/projects/{record_id}'),
}

# These adapters use the existing PMS planner/approval/worker rather than
# reimplementing task mutations in the cross-module executor.
PMS_PERMISSIONS=('pms_manage_tasks','pms_manage_projects','pms_admin')
TOOLS.update({
    'pms.task_plan': Tool('PMS','POST','/ai-operator/workbench/plans/preview','Prepare all task changes, assignment, dates, sprints, dependencies, comments and checklist actions. They use the existing PMS executor.',PMS_PERMISSIONS,
        ('plan','mode'),'app.ai_operator.pms_agent:TaskActions',project_target=True),
    'pms.kickoff': Tool('PMS','POST','/ai-operator/setup/preview','Create a work breakdown: project, milestones, tasks, subtasks and blockers. Omit record_id for a NEW project; set record_id to add work to the selected project.',PMS_PERMISSIONS,
        ('plan',),'app.ai_operator.pms_agent:Kickoff',project_target=True,optional_project=True),
    'pms.schedule': Tool('PMS','POST','/ai-operator/workbench/schedule','Suggest dates using current estimates, all dependency types, working weekdays and holidays. Accepts relative start_date; draft is frozen for review.',PMS_PERMISSIONS,
        ('task_ids','start_date'),'app.ai_operator.pms_agent:Schedule',project_target=True),
    'pms.remember': Tool('PMS','POST','/ai-operator/workbench/items','Remember a private project preference, decision, term or constraint after review.',PMS_PERMISSIONS,
        ('title','text','category'),'app.ai_operator.pms_agent:Remember',project_target=True),
    'pms.save_playbook': Tool('PMS','POST','/ai-operator/workbench/items','Save a reusable explicit task plan with fixed targets.',PMS_PERMISSIONS,
        ('title','plan'),'app.ai_operator.pms_agent:Playbook',project_target=True),
    'pms.run_playbook': Tool('PMS','POST','/ai-operator/workbench/items','Prepare a saved playbook against current records and permissions.',PMS_PERMISSIONS,
        ('playbook_id',),'app.ai_operator.pms_agent:PlaybookRun',project_target=True),
    'pms.undo': Tool('PMS','POST','/ai-operator/workbench/runs','Prepare supported inverse actions from a completed PMS task run. Changed records reject undo; unsupported inverses are disclosed.',PMS_PERMISSIONS,
        ('run_id',),'app.ai_operator.pms_agent:Undo',project_target=True),
    'pms.watch': Tool('PMS','POST','/ai-operator/monitors','Create a delivery monitor for overdue, blocked or unassigned work.',PMS_PERMISSIONS,
        ('name','interval_minutes','enabled'),'app.ai_operator.pms_agent:Watch',project_target=True),
    'pms.event_rule': Tool('PMS','POST','/ai-operator/workbench/items','Create a rule using an existing playbook. Autonomous status/priority updates require a separately enabled administrator policy; this tool cannot enable it.',PMS_PERMISSIONS,
        ('title','playbook_id','trigger','enabled','autonomous'),'app.ai_operator.pms_agent:EventRule',project_target=True),
})


def schema_for(tool):
    if tool.model:
        module, name = tool.model.split(':')
        return getattr(import_module(module), name)
    return None


def validate_payload(tool, payload):
    if set(payload) - set(tool.fields):
        raise HTTPException(422, 'Tool contains unsupported fields')
    model = schema_for(tool)
    if model:
        try:
            model.model_validate(payload)
        except ValueError:
            raise HTTPException(422, 'Tool payload is incomplete or invalid') from None
    if tool.method != 'GET' and not payload:
        raise HTTPException(422, 'Action payload is empty')


def catalog():
    return [{'name': name, 'module': t.module, 'description': t.description, 'approval_required': t.method != 'GET',
             'record_id_required': '{record_id}' in t.path or (t.project_target and not t.optional_project), 'record_id_optional':t.optional_project,'fields': list(t.fields),
             'payload_schema': schema_for(t).model_json_schema() if t.model else None} for name, t in TOOLS.items()]


# Never forward arbitrary employee/customer records into a provider prompt.
SAFE_FIELDS = {'id', 'employee_id', 'employee_code', 'first_name', 'last_name', 'full_name', 'display_name', 'name', 'title',
    'status', 'priority', 'department', 'department_name', 'designation', 'job_title', 'leave_type_id', 'leave_type',
    'code', 'year', 'allocated', 'used', 'pending', 'available', 'carried_forward', 'from_date', 'to_date', 'days_count',
    'due_date', 'start_date', 'created_at', 'task_key', 'project_id', 'workspace_id', 'amount', 'total_amount', 'balance_amount',
    'currency', 'invoice_number', 'quantity', 'stock_quantity', 'unit_price', 'stage_id', 'total', 'totalAssets', 'totalLiabilities',
    'totalIncome', 'totalExpenses', 'cashAndBankBalance', 'receivablesOutstanding', 'payablesOutstanding',
    'overdueReceivables', 'overduePayables', 'booksStatus', 'totalInvoices', 'totalRevenue', 'totalClients', 'totalSalesOrders',
    'items', 'data', 'stats', 'summary', 'total_sales', 'total_invoices', 'outstanding_amount', 'total_receipts', 'sales_orders'}
SAFE_FIELDS.update({'total_sales_orders', 'pending_approvals', 'confirmed_sales_orders', 'active_contracts', 'active_engagements',
    'active_billing_plans', 'invoice_drafts_pending', 'approved_invoices', 'sent_invoices', 'total_invoiced_value',
    'total_collected_value', 'outstanding_value', 'overdue_value', 'collection_risk', 'gross_margin', 'cash_margin',
    'profitability_summary', 'margin_status', 'recent_invoices', 'total_count'})


def minimize(value: Any, depth=0):
    if depth > 5:
        return None
    if isinstance(value, dict):
        return {k: minimize(v, depth+1) for k, v in value.items() if k in SAFE_FIELDS}
    if isinstance(value, list):
        return [minimize(v, depth+1) for v in value[:50]]
    return value[:300] if isinstance(value, str) else value
