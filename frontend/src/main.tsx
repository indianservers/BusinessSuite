import React from "react";
import { recoverChunkLoad } from "./lib/chunk-recovery";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./App.tsx";
import {useAuthStore} from "./store/authStore";
import AsyncProgress from "./components/app/AsyncProgress";
import RouteProgress from "./components/app/RouteProgress";
import "./index.css";
import "./design-system/premium.css";
import { applyTheme, useThemeStore } from "./store/themeStore.ts";

const { theme } = useThemeStore.getState();
applyTheme(theme);

window.addEventListener("vite:preloadError", (event: Event & { payload?: unknown }) => {
  if (recoverChunkLoad(event.payload)) event.preventDefault();
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (useThemeStore.getState().theme === "system") {
    applyTheme("system");
  }
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 2, // 2 minutes
      retry: (failureCount, error: unknown) => {
        if ((error as { response?: { status?: number } })?.response?.status === 401) return false;
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});

// Statistics caches must not survive an identity, tenant or permission-context switch.
const statisticsContext=()=>{const u=useAuthStore.getState().user;return JSON.stringify([u?.id,u?.access?.companyId,u?.role,u?.is_superuser,u?.access?.grants])};
let activeStatisticsContext=statisticsContext();
useAuthStore.subscribe(()=>{const next=statisticsContext();if(next!==activeStatisticsContext){activeStatisticsContext=next;void queryClient.cancelQueries();queryClient.clear()}});
window.addEventListener("suite:organization-changed",()=>{void queryClient.cancelQueries();queryClient.clear()});
let statisticsRefresh:number|undefined;
window.addEventListener("suite:metrics-changed",()=>{window.clearTimeout(statisticsRefresh);statisticsRefresh=window.setTimeout(()=>{void queryClient.invalidateQueries({predicate:query=>/dashboard|headcount|statistics|stats|summary|metrics|count|overview|portfolio|analytics|notification|people-workspace|report|approval|hr-work/i.test(JSON.stringify(query.queryKey))})},180)});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AsyncProgress />
        <RouteProgress />
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").then((registration) => {
      registration.update().catch(() => undefined);
      if (registration.waiting) {
        registration.waiting.postMessage({ type: "SKIP_WAITING" });
      }
    }).catch(() => undefined);
  });
}
