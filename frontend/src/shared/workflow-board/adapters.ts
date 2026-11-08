import { api } from "@/services/api";
import { ageingStage, workflowDeadline, type WorkflowData, type WorkflowFacet, type WorkflowModule, type WorkflowRecord, type WorkflowStage } from "./model";

type Row = Record<string, unknown>;
type Params = Record<string, string | number | undefined>;
const MAX_RECORDS = 1000;
const row = (value: unknown): Row => value && typeof value === "object" && !Array.isArray(value) ? value as Row : {};
const text = (value: unknown) => value == null ? "" : String(value);
const numeric = (value: unknown) => value != null && value !== "" && Number.isFinite(Number(value)) ? Number(value) : undefined;
const rows = (value: unknown): Row[] => (Array.isArray(value) ? value : Array.isArray(row(value).items) ? row(value).items as unknown[] : []).map(row);
const label = (value: string) => value.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
const earliestDeadline = (...values: unknown[]) => values.map(text).filter(v => v && Number.isFinite(workflowDeadline(v))).sort((a, b) => workflowDeadline(a) - workflowDeadline(b))[0];
const facet = (id: unknown, name: unknown, noun: string): WorkflowFacet[] => id != null && id !== "" ? [{ id: text(id), label: text(name) || `${noun} #${id}` }] : [];
const baseRecord = (r: Row): Pick<WorkflowRecord, "id" | "title" | "owners" | "teams" | "priority" | "blocked" | "awaitingApproval"> => ({
  id: text(r.id), title: text(r.title || r.name || `Record #${r.id}`),
  owners: facet(r.owner_user_id || r.assigned_user_id, r.owner_name || r.assigned_user_name, "User"),
  teams: facet(r.assigned_team_id || r.team_id, r.team_name, "Team"),
  priority: text(r.priority), blocked: r.blocked === true || /^blocked$/i.test(text(r.status)),
  awaitingApproval: /^(pending_approval|awaiting approval|pending approval)$/i.test(text(r.status)),
});
function addObservedStages(stages: WorkflowStage[], records: WorkflowRecord[]) {
  return [...stages, ...[...new Set(records.map(r => r.stageId))].filter(id => !stages.some(s => s.id === id)).map(id => ({ id, name: label(id) || "Unassigned stage" }))];
}

/** Read domain endpoints with their existing tenant/branch/record access checks.
 * Pagination is explicit; dashboard totals never imply an unseen full dataset.
 */
async function readPages(path: string, signal: AbortSignal, params: Params = {}, mode: "page" | "pms" | "offset" | "single" = "page") {
  const items: Row[] = [];
  let metadata: Row = {}, truncated = false;
  for (let page = 1; items.length < MAX_RECORDS; page++) {
    const pageSize = mode === "pms" ? 200 : 100;
    const paging = mode === "pms" ? { page, pageSize } : mode === "offset" ? { offset: (page - 1) * pageSize, limit: pageSize } : { page, per_page: pageSize };
    const response = await api.get<unknown>(path, { params: { ...params, ...paging }, signal, progress: false, recordCache: false });
    const batch = rows(response.data);
    if (page === 1) metadata = row(response.data);
    const seen = new Set(items.map(r => text(r.id)));
    const fresh = batch.filter(r => !seen.has(text(r.id)));
    items.push(...fresh.slice(0, MAX_RECORDS - items.length));
    const total = numeric(row(response.data).total);
    // Some domain APIs return an unpaginated array; it is already complete.
    if (mode === "single" || Array.isArray(response.data) && path !== "/recruitment/candidates") { truncated = batch.length > MAX_RECORDS || total != null && total > items.length; break; }
    if (total != null ? items.length >= total : batch.length < pageSize) break;
    if (!fresh.length) { truncated = true; break; }
    if (items.length >= MAX_RECORDS) truncated = true;
  }
  return { items, metadata, truncated };
}

export const workflowTitles: Record<WorkflowModule, string> = {
  crm: "Sales pipeline", hrms: "Hiring pipeline", pms: "Work delivery pipeline", srm: "Sales order pipeline", fam: "Collections pipeline", power_apps: "Approvals pipeline",
};

export async function loadWorkflow(module: WorkflowModule, signal: AbortSignal, environment = "development", workspaceId?: number): Promise<WorkflowData> {
  if (module === "crm") {
    const [deals, stages, pipelines] = await Promise.all([
      readPages("/crm/deal-workspace/query", signal, { sort: "next_follow_up_at", direction: "asc" }),
      readPages("/crm/deal-workspace/pipeline-stages", signal),
      readPages("/crm/deal-workspace/pipelines", signal),
    ]);
    const pipelineName = (id: unknown) => text(pipelines.items.find(p => p.id === id)?.name);
    const records: WorkflowRecord[] = deals.items.map(r => ({ ...baseRecord(r),
      stageId: text(r.stage_id || "unassigned"), href: `/crm/deals/${r.id}`,
      subtitle: text(r.company_name), date: text(r.expected_close_date) || undefined,
      due: earliestDeadline(r.next_follow_up_at, r.expected_close_date),
      amount: numeric(r.amount), currency: text(r.currency) || undefined,
      closed: /^(won|lost|closed|cancelled)$/i.test(text(r.status)),
      canChangeStage: deals.metadata.can_manage === true,
    }));
    return { title: workflowTitles.crm, stages: addObservedStages(stages.items.map(s => ({ id: text(s.id), name: pipelines.items.length > 1 ? `${pipelineName(s.pipeline_id)} · ${s.name}` : text(s.name) })), records), records, totalLabel: "Value", dateLabel: "Expected close", workspaceHref: "/crm/pipeline", note: "Amounts grouped by currency. Stage changes use the reviewed deal workflow.", truncated: deals.truncated || stages.truncated };
  }
  if (module === "hrms") {
    const [candidates, jobs] = await Promise.all([readPages("/recruitment/candidates", signal), readPages("/recruitment/jobs", signal, {}, "single")]);
    const records: WorkflowRecord[] = candidates.items.map(r => {
      const job = jobs.items.find(j => j.id === r.job_id) || {};
      return { ...baseRecord(r), title: [r.first_name, r.last_name].filter(Boolean).join(" ") || text(r.name || r.email), stageId: text(r.status || "Applied"),
        subtitle: text(job.title || r.email), href: `/hrms/recruitment?candidate=${r.id}`,
        owners: facet(job.hiring_manager_id, job.hiring_manager_name, "Hiring manager"), teams: facet(job.department_id, job.department_name, "Department"),
        date: text(r.applied_at) || undefined, closed: /^(hired|rejected|withdrawn)$/i.test(text(r.status)), jobId: numeric(r.job_id),
      };
    });
    return { title: workflowTitles.hrms, stages: addObservedStages(["Applied", "Screening", "Interview", "Assessment", "Offer", "Hired", "Rejected", "Withdrawn"].map(id => ({ id, name: id })), records), records, totalLabel: "Candidates", dateLabel: "Applied", workspaceHref: "/hrms/recruitment", note: "Owners are job hiring managers; teams are hiring departments. Hiring and employee conversion remain separate.", truncated: candidates.truncated || jobs.truncated };
  }
  if (module === "pms") {
    const tasks = await readPages("/project-management/dashboard-workflow", signal, { workspaceId }, "single");
    const records: WorkflowRecord[] = tasks.items.map(r => ({ ...baseRecord(r),
      stageId: text(r.status || "Backlog"), subtitle: text(r.project_name), href: `/pms/tasks/${r.id}`,
      owners: Array.isArray(r.assignees) && r.assignees.length ? (r.assignees as unknown[]).map(row).map(a => ({ id: text(a.id), label: text(a.name) || `User #${a.id}` })) : facet(r.assignee_user_id, r.assignee_name, "User"),
      teams: Array.isArray(r.group_targets) ? (r.group_targets as unknown[]).map(row).filter(g => g.kind === "teams").map(g => ({ id: text(g.id), label: text(g.name) })) : [],
      date: text(r.due_date) || undefined, due: text(r.due_date) || undefined, effort: numeric(r.estimated_hours),
      closed: /^(done|completed|closed|resolved|cancelled|canceled|rejected)$/i.test(text(r.status)),
    }));
    return { title: workflowTitles.pms, stages: addObservedStages(["Backlog", "To Do", "In Progress", "In Review", "Done"].map(id => ({ id, name: id })), records), records, totalLabel: "Effort", dateLabel: "Due", workspaceHref: workspaceId ? `/pms/tasks?workspaceId=${workspaceId}` : "/pms/tasks", note: "Open a task for its project-specific transitions, approvals and blockers.", truncated: tasks.truncated };
  }
  if (module === "srm") {
    const orders = await readPages("/srm/sales-orders", signal);
    const records: WorkflowRecord[] = orders.items.map(r => ({ ...baseRecord(r), title: text(r.order_number || r.title || `Order #${r.id}`), stageId: text(r.status || "draft").toLowerCase(),
      href: `/srm/sales-orders/${r.id}`, subtitle: text(r.customer_name || (r.customer_id ? `Customer #${r.customer_id}` : "")),
      date: text(r.expected_end_date || r.created_at) || undefined, due: text(r.expected_end_date) || undefined,
      amount: numeric(r.total_amount), currency: text(r.currency) || undefined, closed: /^(closed|cancelled|canceled)$/i.test(text(r.status)),
      canChangeStage: ["draft", "approved"].includes(text(r.status).toLowerCase()) && row(r.metadata_json).source !== "pos",
    }));
    return { title: workflowTitles.srm, stages: addObservedStages(["draft", "pending_approval", "approved", "confirmed", "closed", "cancelled"].map(id => ({ id, name: label(id) })), records), records, totalLabel: "Value", dateLabel: "Expected end / created", workspaceHref: "/srm/sales-orders", note: "Document stages reflect recorded order status. Dates use expected end, falling back to creation date. Open an order for permitted approval and fulfilment actions.", truncated: orders.truncated || orders.items.length >= 200 };
  }
  if (module === "fam") {
    const [bills, dashboard] = await Promise.all([readPages("/fam/ar/outstanding", signal, {}, "single"), api.get<Row>("/fam/dashboard", { signal, progress: false })]);
    const currency = text(dashboard.data.baseCurrency) || undefined;
    const records: WorkflowRecord[] = bills.items.filter(r => (numeric(r.outstanding_amount) || 0) > 0).map(r => ({ ...baseRecord(r), title: text(r.bill_number || `Bill #${r.id}`),
      stageId: ageingStage(text(r.due_date) || undefined), href: r.voucher_id ? `/fam/vouchers/${r.voucher_id}` : `/fam/parties/${r.party_id}`,
      subtitle: `Party #${r.party_id}`, date: text(r.due_date) || undefined, due: text(r.due_date) || undefined, amount: numeric(r.outstanding_amount), currency,
    }));
    return { title: workflowTitles.fam, stages: [{ id: "upcoming", name: "Upcoming" }, { id: "today", name: "Due today" }, { id: "1-30", name: "1–30 days overdue" }, { id: "31-60", name: "31–60 days overdue" }, { id: "60+", name: "60+ days overdue" }, ...(records.some(r => r.stageId === "undated") ? [{ id: "undated", name: "No due date" }] : [])], records, totalLabel: "Outstanding", dateLabel: "Due", workspaceHref: "/fam/ar/outstanding", note: "Outstanding bill references in book currency. Ageing updates by calendar day; payments and allocations change balances.", truncated: bills.truncated };
  }
  const requests = await readPages("/power-apps/approvals/requests", signal, { environment, scope: "all", sort: "due" }, "offset");
  const records: WorkflowRecord[] = requests.items.map(r => ({ ...baseRecord(r), stageId: text(r.status || "Pending"),
    href: `/power-apps/approvals/inbox?environment=${encodeURIComponent(environment)}&request=${r.id}`, subtitle: [r.request_type, r.current_stage, r.requester_name].filter(Boolean).join(" · "),
    owners: Array.isArray(r.assigned_user_ids) ? r.assigned_user_ids.map(id => ({ id: text(id), label: `Approver #${id}` })) : [],
    date: text(r.sla_due_at) || undefined, due: text(r.sla_due_at) || undefined,
    closed: /^(approved|rejected|cancelled|canceled|expired)$/i.test(text(r.status)),
    awaitingApproval: r.status === "Pending", blocked: r.status === "Resolution Required",
  }));
  return { title: workflowTitles.power_apps, stages: addObservedStages(["Pending", "Resolution Required", "Approved", "Rejected", "Cancelled", "Expired"].map(id => ({ id, name: id })), records), records, totalLabel: "Requests", dateLabel: "SLA due", workspaceHref: `/power-apps/approvals/inbox?environment=${encodeURIComponent(environment)}`, note: `${label(environment)} environment. Open a request for assigned decisions, evidence and approval rules.`, truncated: requests.truncated };
}
