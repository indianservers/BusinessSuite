import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
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
sessionStorage.setItem("suite-branch", params.get("branch") || "1");
const rows = params.has("empty") ? [] : [
  { id: 101, name: "Client delivery", role: "Owner", owners: ["delivery@example.test"], member_count: 8, project_count: 3, task_count: 24, completed_task_count: 16, created_at: "2026-10-14T10:00:00Z" },
  { id: 102, name: "Product engineering", role: "Member", owners: ["engineering@example.test"], member_count: 5, project_count: 2, task_count: 12, completed_task_count: 5, created_at: "2026-11-01T10:00:00Z" },
  { id: 103, name: "Operations", role: "Admin", owners: ["operations@example.test"], member_count: 4, project_count: 1, task_count: 0, completed_task_count: 0, created_at: "2026-11-05T10:00:00Z" },
];
// Deterministic browser-only fixtures; never contact a business database.
api.defaults.adapter = async config => {
  if (params.has("error") || (window as Window & { __workspaceQaDeny?: boolean }).__workspaceQaDeny) throw { response: { status: 403, data: { detail: "You do not have access to these workspaces." } }, config };
  const summaries: Record<string, unknown> = {
    "/crm/dashboard": { summary: { leads: 17, openDeals: 6, overdueActivities: 2 } },
    "/employees/workbench/home?scope=organization": { employee_count: 42, pending_counts: { approvals: 7 }, missing_punches: 3 },
    "/srm/dashboard": { total_sales_orders: 31, pending_approvals: 4, approved_invoices: 23 },
    "/fam/dashboard": { currentFinancialYear: { name: "FY 2026–27" }, booksStatus: "open", baseCurrency: "INR" },
  };
  if (config.url && summaries[config.url]) return { data: params.has("missing-metrics") ? {} : summaries[config.url], status: 200, statusText: "OK", headers: {}, config };
  if (config.url !== "/project-management/workspaces") throw Error(`Unexpected QA request: ${config.url}`);
  let data: unknown = [...rows];
  if (config.method === "post") { const body = typeof config.data === "string" ? JSON.parse(config.data) : config.data; const workspace = { id: 104, name: body.name, role: "Owner", owners: ["qa@example.test"], member_count: 1, project_count: 0, task_count: 0, completed_task_count: 0 }; rows.push(workspace); data = workspace; }
  return { data, status: 200, statusText: "OK", headers: {}, config };
};
const content = module === "pms" ? <ProjectWorkspaceDirectory /> : <OperationalWorkspaceDirectory module={module as "crm" | "hrms" | "srm" | "fam"} />;
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={[`/${module}/workspaces`]}><header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "15px 24px", borderBottom: "1px solid #eee5f7", background: "white" }}><strong style={{ fontSize: 14 }}>Indian Servers Pvt Ltd <small style={{ display: "block", color: "#7f6c97", fontWeight: 400 }}>Business Suite · Browser fixture</small></strong><WorkspaceDirectoryMenu /></header>{params.has("frame") && (module === "pms" || module === "crm") ? <ModuleWorkspaceFrame module={module}>{content}</ModuleWorkspaceFrame> : content}</MemoryRouter></QueryClientProvider>);
