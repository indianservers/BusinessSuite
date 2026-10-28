// Browser-test fixture. Not referenced by application routes.
import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Employee360Panel from "../src/apps/hrms/pages/employees/Employee360Panel";
import { useAuthStore } from "../src/store/authStore";
import "../src/index.css";
useAuthStore.setState({ user: { id: 1, employee_id: 7, role: "admin", email: "test@example.com", is_superuser: true }, accessToken: "test" });
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={client}><Employee360Panel employeeId={7} isOwnProfile onOpenTab={tab => { (window as unknown as { openedTab: string }).openedTab = tab; }} /></QueryClientProvider>,
);
