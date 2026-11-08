import React from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Directory from "@/apps/project-management/pages/WorkspaceDirectoryPage";
import Frame from "@/shared/workspace/ModuleWorkspaceFrame";
import { useAuthStore } from "@/store/authStore";
import "@/index.css";
useAuthStore.setState({
  isAuthenticated: true,
  isHydrated: true,
  accessToken: "fixture",
  user: { id: 1, email: "qa@example.test", role: "admin", is_superuser: true },
});
localStorage.setItem("pms-workspace-1", "2");
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={["/pms/workspaces"]}>
      <Frame module="pms">
        <Directory />
      </Frame>
    </MemoryRouter>
  </QueryClientProvider>,
);
