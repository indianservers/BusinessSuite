// Isolated UI acceptance fixture. All API traffic is replaced in this page only.
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import ModuleWorkflowBoard from "@/shared/workflow-board/ModuleWorkflowBoard";
import type { WorkflowModule } from "@/shared/workflow-board/model";
import "@/index.css";

let failing = false, writable = true, moveFails = false, branchReadOnly = false;
const due = (offset: number) => { const d = new Date(); d.setDate(d.getDate() + offset); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const grants = { crm: { enabled: true, role: "admin", scope: "all", actions: ["view", "edit"], permissions: [] }, hrms: { enabled: true, role: "admin", scope: "all", actions: ["view", "edit"], permissions: ["recruitment_manage"] }, project_management: { enabled: true, role: "admin", scope: "all", actions: ["view", "edit"], permissions: [] } };
useAuthStore.setState({ isAuthenticated: true, isHydrated: true, user: { id: 90263, email: "workflow-qa@example.test", role: "admin", is_superuser: false, access: { companyId: 90263, managed: true, grants, modules: [], memberships: [], isAccessAdmin: false, isGlobalAdmin: false } } });
api.defaults.adapter = async config => {
  const url = config.url || "";
  let data: unknown = { items: [], total: 0 };
  if (url === "/branches/context") data = { company_id: 90263, selected: 1, all_branches: false, manage_access: false, branches: [{ id: 1, name: "QA branch", code: "QA", can_write: true }] };
  else if (failing) throw { response: { status: 503, data: { detail: "Workflow fixture unavailable" } }, config };
  else if (url.endsWith("/pipeline-stages")) data = { items: [{ id: 1, name: "Qualification", pipeline_id: 1 }, { id: 2, name: "Proposal", pipeline_id: 1 }], total: 2 };
  else if (url.endsWith("/pipelines")) data = { items: [{ id: 1, name: "Sales" }], total: 1 };
  else if (url.endsWith("/query")) data = { can_manage: writable, total: 5, items: [
    { id: 1, name: "Routine opportunity", stage_id: 1, amount: 400, currency: "INR", owner_user_id: 1, owner_name: "Alex", assigned_team_id: 1, expected_close_date: due(5), status: "Open" },
    { id: 2, name: "Urgent opportunity", stage_id: 1, amount: 100, currency: "USD", owner_user_id: 2, owner_name: "Jamie", assigned_team_id: 2, expected_close_date: due(-3), status: "Open" },
    { id: 3, name: "Blocked opportunity", stage_id: 1, amount: 500, currency: "INR", owner_user_id: 1, owner_name: "Alex", assigned_team_id: 1, blocked: true, expected_close_date: due(4), status: "Open" },
    { id: 4, name: "Approval opportunity", stage_id: 1, amount: 600, currency: "INR", expected_close_date: due(3), status: "pending_approval" },
    { id: 5, name: "Proposal opportunity", stage_id: 2, amount: 50, currency: "USD", expected_close_date: due(2), status: "Open" },
  ] };
  else if (url === "/recruitment/jobs") data = [{ id: 1, title: "Engineer", hiring_manager_id: 4, department_id: 2 }];
  else if (url === "/recruitment/candidates") data = [{ id: 6, job_id: 1, first_name: "Taylor", last_name: "Candidate", email: "taylor@example.test", status: "Applied", applied_at: due(-2) }];
  else if (url.includes("/configuration")) data = { stages: [{ name: "Applied" }, { name: "Screening" }, { name: "Interview" }] };
  else if (url === "/project-management/dashboard-workflow") data = { total: 2, items: [{ id: 7, title: "Urgent delivery task", project_name: "Delivery", status: "In Progress", due_date: due(-2), estimated_hours: 8, assignees: [{ id: 2, name: "Jamie" }], group_targets: [{ id: 1, kind: "teams", name: "Delivery team" }] }, { id: 8, title: "Completed delivery task", status: "Done", due_date: due(-3), estimated_hours: 2 }] };
  else if (url.endsWith("/transition-approvals")) data = { can_request: writable, transitions: [{ target: "In Review", approval_required: true }, { target: "Done", approval_required: false }] };
  else if (url === "/srm/sales-orders") data = [{ id: 9, order_number: "SO-009", customer_name: "Example customer", total_amount: 4000, currency: "INR", status: "pending_approval", expected_end_date: due(-1), assigned_user_id: 2 }];
  else if (url === "/fam/ar/outstanding") data = { items: [{ id: 10, bill_number: "INV-010", party_id: 12, voucher_id: 13, due_date: due(-35), outstanding_amount: 2400 }] };
  else if (url === "/fam/dashboard") data = { baseCurrency: "INR" };
  else if (url === "/power-apps/approvals/requests") data = { total: 2, items: [{ id: 11, title: "Purchase approval", status: "Pending", sla_due_at: due(-2), assigned_user_ids: [2], requester_name: "Alex", current_stage: "Finance review" }, { id: 12, title: "Evidence missing", status: "Resolution Required", assigned_user_ids: [3] }] };
  if (config.method && config.method !== "get") {
    if (moveFails) throw { response: { status: 409, data: { detail: "Required evidence is missing" } }, config };
    data = { ok: true };
    document.body.dataset.workflowMutation = `${config.method}:${url}:${JSON.stringify(config.data)}`;
  }
  return { data, status: 200, statusText: "OK", headers: {}, config };
};
const client = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } } });
function Fixture() {
  const module = (new URLSearchParams(location.search).get("module") || "crm") as WorkflowModule;
  const [version, setVersion] = useState(0);
  return <main className="p-4 mx-auto max-w-7xl"><h1 className="text-2xl font-semibold">Workflow Board acceptance</h1><p className="text-sm mb-4">Isolated fixture data · dashboard component verification</p>
    <nav className="flex flex-wrap gap-4 mb-4">{["crm", "hrms", "pms", "srm", "fam", "power_apps"].map(m => <a key={m} href={`?module=${m}`}>{m}</a>)}</nav>
    <div className="grid grid-cols-2 gap-3 mb-3" aria-label="Dashboard KPIs"><div className="border rounded p-4">Active workflow</div><div className="border rounded p-4">Items requiring attention</div></div>
    <ModuleWorkflowBoard key={version} module={module} environment="development" workspaceId={module === "pms" ? 5 : undefined} />
    <div className="flex flex-wrap gap-3 mt-6"><button onClick={() => { failing = !failing; void client.invalidateQueries(); }}>Toggle service failure</button><button onClick={() => { writable = !writable; const u = useAuthStore.getState().user!; useAuthStore.getState().setUser({ ...u, access: { ...u.access!, grants: Object.fromEntries(Object.entries(grants).map(([k, v]) => [k, { ...v, actions: writable ? ["view", "edit"] : ["view"] }])) } }); client.clear(); setVersion(v => v + 1); }}>Toggle read-only access</button><button onClick={() => { moveFails = !moveFails; }}>Toggle transition rejection</button><button onClick={() => { branchReadOnly = !branchReadOnly; const u = useAuthStore.getState().user!; useAuthStore.getState().setUser({ ...u, access: { ...u.access!, grants: Object.fromEntries(Object.entries(grants).map(([k, v]) => [k, { ...v, actions: branchReadOnly ? ["view"] : ["view", "edit"] }])) } }); }}>Toggle branch read-only</button></div>
  </main>;
}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><BrowserRouter><Fixture /></BrowserRouter></QueryClientProvider>);
