import React, { useState } from "react";
import ReactDOM from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Workspace from "../../src/apps/crm/CRMTasksWorkspace";
import { CRMQuickCreate } from "../../src/apps/crm/SalesActions";
import { useAuthStore } from "../../src/store/authStore";
import "../../src/index.css";

useAuthStore.setState({ user: { id: 7, email: "me@example.test", name: "Me", role: "admin", is_superuser: true }, accessToken: "qa", isAuthenticated: true });
function Fixture() {
  const [open, setOpen] = useState(false);
  return <><button onClick={() => setOpen(true)}>Left menu task</button><Workspace legacyKey="productivity:crm:7:v1" onNotes={() => {}}/>{open && <CRMQuickCreate type="task" close={() => setOpen(false)} saved={() => {}}/>}</>;
}
ReactDOM.createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/crm/tasks"]}><Fixture/></MemoryRouter></QueryClientProvider>);
