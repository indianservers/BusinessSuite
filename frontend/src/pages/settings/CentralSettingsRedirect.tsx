import { Navigate, useLocation } from "react-router-dom";
import SettingsHubPage from "@/pages/SettingsHubPage";

/** Keep saved module links working while using one canonical configuration editor. */
export default function CentralSettingsRedirect({ section }: { section: string }) {
  const location = useLocation();
  const module = location.pathname.split("/")[1];
  const labels: Record<string, string> = { crm: "CRM", pms: "Projects", srm: "Sales & inventory", fam: "Finance" };
  if (labels[module]) return <SettingsHubPage sectionId={section} moduleHome={`/${module}`} moduleLabel={labels[module]} />;
  return <Navigate replace to={`/settings/${section}${location.search}${location.hash}`}/>;
}
