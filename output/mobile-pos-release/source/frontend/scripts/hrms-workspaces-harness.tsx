// Local browser acceptance fixture; not included in application routes.
import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import TeamWorkspace from "../src/apps/hrms/pages/dashboard/TeamWorkspace";
import AssetsPage from "../src/apps/hrms/pages/assets/AssetsPage";
import ExpensesPage from "../src/apps/hrms/pages/expenses/ExpensesPage";
import GuidedPayroll from "../src/apps/hrms/pages/payroll/GuidedPayroll";
import ReportSchedules from "../src/apps/hrms/pages/reports/ReportSchedules";
import { useAuthStore } from "../src/store/authStore";
import "../src/index.css";
useAuthStore.setState({ user: { id: 1, employee_id: 7, role: "admin", email: "qa@example.com", is_superuser: true }, accessToken: "test" });
const screen = new URLSearchParams(location.search).get("screen");
const content = screen === "team" ? <TeamWorkspace /> : screen === "assets" ? <AssetsPage /> : screen === "expenses" ? <ExpensesPage /> : screen === "reports" ? <ReportSchedules /> : <GuidedPayroll onOpenTool={() => {}} />;
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><main style={{ padding: 16 }}>{content}</main></MemoryRouter></QueryClientProvider>);
