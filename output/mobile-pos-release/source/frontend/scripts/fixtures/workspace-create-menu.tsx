import React, { lazy, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, useLocation } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "../../src/store/authStore";
import ModuleNewMenu from "../../src/components/app/ModuleNewMenu";
import NewMenu from "../../src/components/app/NewMenu";
import CreationOutcome from "../../src/shared/creation/CreationOutcome";
import { CreationDialogEnhancements } from "../../src/shared/creation/CreationDialogEnhancements";
import { Toaster } from "../../src/components/ui/toaster";
const Leave = lazy(() => import("../../src/apps/hrms/pages/leave/LeavePage"));
const Expense = lazy(() => import("../../src/apps/hrms/pages/expenses/ExpenseClaimForm"));
const Employee = lazy(() => import("../../src/apps/hrms/pages/employees/AddEmployeePage"));
const Attendance = lazy(() => import("../../src/apps/hrms/workbench/HRDailyWork"));
const Docs = lazy(() => import("../../src/apps/project-management/pages/DocsPage"));
const Import = lazy(() => import("../../src/shared/data-transfer/ImportWorkspace"));
import "../../src/index.css";
const params = new URLSearchParams(window.location.search);
const readOnly = params.has("readonly");
const grant = { enabled: true, role: "Employee", scope: "own", permissions: [], actions: ["view"] };
useAuthStore.setState({ user: { id: 1, employee_id: 101, email: "qa@example.test", role: params.get("role") || "admin", is_superuser: !params.has("role") && !readOnly, ...(readOnly ? {access: {managed:true,companyId:1,grants:{project_management:grant,crm:grant,hrms:grant},modules:[],isAccessAdmin:false,isGlobalAdmin:false,memberships:[]}} : {}) }, isAuthenticated: true, isHydrated: true });
function Harness() {
  const location = useLocation();
  const screen = params.get("screen");
  return <><ModuleNewMenu>{params.has("floating") ? actions => <NewMenu actions={actions} floating/> : undefined}</ModuleNewMenu><output data-testid="destination">{location.pathname + location.search + location.hash}</output><CreationOutcome/><CreationDialogEnhancements/><Toaster/><Suspense fallback={<p>Loading test screen…</p>}>{screen === "leave" ? <Leave/> : screen === "expense" ? <Expense employeeId={101}/> : screen === "employee" ? <Employee/> : screen === "attendance" ? <Attendance/> : screen === "docs" ? <Docs/> : screen === "import" ? <Import module="hrms"/> : null}</Suspense></>;
}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[params.get("path") || "/crm/records"]}><Harness /></MemoryRouter></QueryClientProvider>);
