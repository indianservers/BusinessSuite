// Isolated acceptance fixture; not included in application routes.
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TaskExecutionPanel from "../src/apps/project-management/components/TaskExecutionPanel";
import { ApprovalInbox } from "../src/apps/power-apps/applications/approvals/ApprovalComponents";
import PersonMembershipEditor from "../src/apps/project-management/components/people/PersonMembershipEditor";
import { FollowUpDialog } from "../src/apps/crm/leads/LeadWorkflow";
import { useAuthStore } from "../src/store/authStore";
import EmployeeActions from "../src/apps/hrms/workbench/EmployeeActions";
import PersonManagementHost from "../src/apps/project-management/components/people/PersonManagementHost";
import HRDailyWork from "../src/apps/hrms/workbench/HRDailyWork";
import "../src/index.css";
useAuthStore.setState({ user: { id: 1, role: "admin", email: "test@example.com", is_superuser: true }, accessToken: "test" });
const screen = new URLSearchParams(location.search).get("screen");
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
const lead = { id: 7, full_name: "Test customer", owner_user_id: 1 } as any;
createRoot(document.getElementById("root")!).render(<BrowserRouter><QueryClientProvider client={client}>
  {screen === "hr-review" ? <HRDailyWork/> : screen === "hr" ? <><EmployeeActions id={7}/><PersonManagementHost/></> : screen === "task" ? <TaskExecutionPanel taskId={7} /> : screen === "approvals" ? <ApprovalInbox environment="development" onOpen={() => {}} /> : screen === "membership" ? <PersonMembershipEditor person={{id: 1, status: "active", workspaces: [], projects: [], permissions: { memberships: true }}} busy={false} mutate={async work => { await work(); return true; }} remove={() => {}} /> : <FollowUpDialog lead={lead} bootstrap={{canAssign: true, userId: 1, owners: [{id: 1, name: "Test owner"}] } as any} close={() => {}} saved={() => {}} />}
</QueryClientProvider></BrowserRouter>);
