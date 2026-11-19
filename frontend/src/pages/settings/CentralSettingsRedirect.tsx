import { Navigate, useLocation } from "react-router-dom";
import { lazyRoute } from "@/lib/lazy-route";
import { Suspense } from "react";
const SettingsHubPage = lazyRoute(() => import("@/pages/SettingsHubPage"));

/** Keep saved module links working while using one canonical configuration editor. */
function CentralSettingsRedirect({ section }: { section: string }) {
  const location = useLocation();
  const module = location.pathname.split("/")[1];
  const labels: Record<string, string> = { crm: "CRM", pms: "Projects", srm: "Sales & inventory", fam: "Finance" };
  if (labels[module]) return <Suspense fallback={<div role="status">Loading settings…</div>}><SettingsHubPage sectionId={section} moduleHome={`/${module}`} moduleLabel={labels[module]} /></Suspense>;
  return <Navigate replace to={`/settings/${section}${location.search}${location.hash}`}/>;
}

export default Object.assign(CentralSettingsRedirect, { preload: SettingsHubPage.preload });
