import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AsyncProgress from "@/components/app/AsyncProgress";
import { QuickDealDialog } from "@/apps/crm/CRMWorkspacePage";
import { useAuthStore } from "@/store/authStore";
import "@/index.css";
useAuthStore.setState({
  isAuthenticated: true,
  isHydrated: true,
  accessToken: "fixture",
  user: { id: 1, email: "qa@example.test", role: "admin", is_superuser: true },
});
function Fixture() {
  const [mode, setMode] = useState<"create" | "edit">();
  return (
    <>
      <AsyncProgress />
      <button onClick={() => setMode("create")}>Start new deal</button>
      <button onClick={() => setMode("edit")}>Edit existing deal</button>
      {mode && (
        <QuickDealDialog
          dealId={mode === "edit" ? 1 : undefined}
          close={() => setMode(undefined)}
          saved={() => {}}
        />
      )}
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient()}>
    <MemoryRouter initialEntries={["/crm/deals"]}>
      <Fixture />
    </MemoryRouter>
  </QueryClientProvider>,
);
