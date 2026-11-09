import { SmartCreationProvider } from "@/shared/creation/SmartCreationProvider";
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Link } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ModuleWorkspaceFrame from "@/shared/workspace/ModuleWorkspaceFrame";
import ProjectWorkspaceDirectory from "@/apps/project-management/pages/ProjectWorkspaceDirectory";
import OperationalWorkspaceDirectory from "@/shared/workspace/OperationalWorkspaceDirectory";
import { WorkspaceDirectoryMenu } from "@/shared/workspace/WorkspaceDirectoryMenu";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import "@/index.css";
const params = new URLSearchParams(window.location.search);
const module = params.get("module") || "pms";
const restricted = params.has("restricted");
useAuthStore.setState({ isAuthenticated: true, isHydrated: true, accessToken: "qa-fixture", user: { id: Number(params.get("user") || 991), email: "qa@example.test", role: restricted ? "employee" : "admin", is_superuser: !restricted, access: { companyId: 1, companyName: "Indian Servers Pvt Ltd", managed: false, grants: {}, modules: [], isAccessAdmin: !restricted, isGlobalAdmin: !restricted, memberships: [] } } });
sessionStorage.setItem("suite-organization", "1");
if (params.has("no-branch")) sessionStorage.removeItem("suite-branch"); else sessionStorage.setItem("suite-branch", params.get("branch") || "1");
const rows = params.has("empty") ? [] : [
  { id: 101, name: "Client delivery", role: "Owner", owners: ["delivery@example.test"], member_count: 8, project_count: 3, task_count: 24, completed_task_count: 16, created_at: "2026-10-14T10:00:00Z" },
  { id: 102, name: "Product engineering", role: "Member", owners: ["engineering@example.test"], member_count: 5, project_count: 2, task_count: 12, completed_task_count: 5, created_at: "2026-11-01T10:00:00Z" },
  { id: 103, name: "Operations", role: "Admin", owners: ["operations@example.test"], member_count: 4, project_count: 1, task_count: 0, completed_task_count: 0, created_at: "2026-11-05T10:00:00Z" },
];
const viewIds = { pms: ["projects", "tasks", "board", "timeline", "workload", "team", "activity", "settings"], crm: ["leads", "contacts", "deals", "activities", "quotes", "reports"], hrms: ["employees", "attendance", "leave", "approvals", "documents", "recruitment"], srm: ["pos", "orders", "products", "stock", "invoices", "collections"], fam: ["accounts", "journals", "receivables", "payables", "reconciliation", "statements"] };
let saved = rows.map(row => ({ ...row, project_count: module === "pms" ? row.project_count : undefined, task_count: module === "pms" ? row.task_count : undefined, completed_task_count: module === "pms" ? row.completed_task_count : undefined, id: String(row.id), owners: row.owners || ["qa@example.test"], description: "A focused space for the team.", icon: "folder", color: "#7632ff", visibility: "private", views: viewIds[module as keyof typeof viewIds], members: [], owner_id: row.role === "Owner" ? 991 : 992, can_manage: row.role !== "Member", can_archive: row.role !== "Member", version: 1, status: "Active", updated_at: row.created_at, activity_count: 1 }));
const events = params.has("empty") ? [] : [{ id: 1, summary: "Workspace created: Client delivery", actor: "qa@example.test", created_at: "2026-11-08T09:00:00Z" }];
api.defaults.adapter = async config => {
  const fail = (status: number, detail: string): never => { throw { response: { status, data: { detail } }, config }; };
  if (params.has("error") || (window as Window & { __workspaceQaDeny?: boolean }).__workspaceQaDeny) fail(403, "You do not have access to these workspaces.");
  const summaries: Record<string, unknown> = {
    "/branches/context": { selected: 1, branches: [{ id: 1, name: "Main branch" }] },
    "/crm/dashboard": { summary: { leads: 17, openDeals: 6, overdueActivities: 2 } },
    "/employees/workbench/home?scope=organization": { employee_count: 42, pending_counts: { approvals: 7 }, missing_punches: 3 },
    "/srm/dashboard": { total_sales_orders: 31, pending_approvals: 4, approved_invoices: 23 },
    "/fam/dashboard": { currentFinancialYear: { name: "FY 2026–27" }, booksStatus: "open", baseCurrency: "INR" },
  };
  let data: unknown;
  const url = config.url || "";
  if (summaries[url]) data = params.has("missing-metrics") ? {} : summaries[url];
  else if (url.endsWith("/activity")) data = events;
  else if (url.endsWith("/eligible-people")) data = [{ user_id: 992, email: "member@example.test" }];
  else if (url.includes("/workspace-directory")) {
    if (config.method === "post" || config.method === "put") {
      const body = typeof config.data === "string" ? JSON.parse(config.data) : config.data;
      const existing = config.method === "put" ? saved.find(row => row.id === url.split("/").pop()) : undefined;
      if (existing && body.expected_version !== existing.version) fail(409, "Workspace changed. Reload before saving.");
      const row = { ...(existing || saved[0] || { role: "Owner", member_count: 1 }), ...body, id: existing?.id || "104", version: (existing?.version || 0) + 1, owner_id: 991, owners: ["qa@example.test"], can_manage: true, can_archive: true, created_at: existing?.created_at || new Date().toISOString(), updated_at: new Date().toISOString() };
      saved = [...saved.filter(item => item.id !== row.id), row];
      events.unshift({ id: events.length + 1, summary: `${existing ? "Workspace updated" : "Workspace created"}: ${row.name}`, actor: "qa@example.test", created_at: new Date().toISOString() });
      data = row;
    } else if (/\/workspace-directory\/[^/]+$/.test(url)) {
      data = saved.find(row => row.id === url.split("/").pop());
      if (!data) fail(404, "Workspace not found");
    } else data = { items: saved, can_create: !restricted };
  } else if (url === "/project-management/workspaces") data = saved;
  else fail(404, `Unexpected fixture request: ${url}`);
  return { data, status: 200, statusText: "OK", headers: {}, config };
};
const content = module === "pms" ? <ProjectWorkspaceDirectory /> : <OperationalWorkspaceDirectory module={module as "crm" | "hrms" | "srm" | "fam"} />;
const CreationWrapper = params.has("smart") ? SmartCreationProvider : ({ children }: { children: React.ReactNode; routes?: unknown[] }) => <>{children}</>;
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[`/${module}/workspaces${params.has("intent") ? "?new=workspace" : ""}`]}><CreationWrapper routes={[]}><header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "15px 24px", borderBottom: "1px solid #eee5f7", background: "white" }}><strong style={{ fontSize: 14 }}>Indian Servers Pvt Ltd <small style={{ display: "block", color: "#7f6c97", fontWeight: 400 }}>Business Suite · Browser fixture</small></strong><div style={{ display: "flex", gap: 12 }}>{params.has("smart") && <Link to={`/${module}/workspaces?new=workspace`}>New workspace shortcut</Link>}<WorkspaceDirectoryMenu /></div></header>{params.has("frame") && (module === "pms" || module === "crm") ? <ModuleWorkspaceFrame module={module}>{content}</ModuleWorkspaceFrame> : content}</CreationWrapper></MemoryRouter></QueryClientProvider>);
