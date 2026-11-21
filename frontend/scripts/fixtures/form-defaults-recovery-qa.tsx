import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FormDefaultsGate from "@/components/forms/FormDefaultsGate";
import { useAuthStore } from "@/store/authStore";

function refreshAccess() {
  const { user, setUser } = useAuthStore.getState();
  if (user) setUser({ ...user, access: {
    companyId: 1, managed: false, grants: {}, modules: [],
    isAccessAdmin: false, isGlobalAdmin: false, memberships: [1],
  } });
}

function switchBranch() {
  sessionStorage.setItem("suite-branch", "2");
  window.dispatchEvent(new Event("suite:branch-changed"));
}

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient()}>
    <button onClick={refreshAccess}>Refresh access</button>
    <button onClick={switchBranch}>Switch branch</button>
    <FormDefaultsGate><label>New record title<input /></label></FormDefaultsGate>
  </QueryClientProvider>,
);
