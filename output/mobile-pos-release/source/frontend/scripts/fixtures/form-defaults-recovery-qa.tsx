import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import FormDefaultsGate from "@/components/forms/FormDefaultsGate";
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={new QueryClient()}>
    <FormDefaultsGate><label>New record title<input /></label></FormDefaultsGate>
  </QueryClientProvider>,
);
