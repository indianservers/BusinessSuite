import { Navigate, useLocation } from "react-router-dom";

/** Keep saved module links working while using one canonical configuration editor. */
export default function CentralSettingsRedirect({ section }: { section: string }) {
  const location = useLocation();
  return <Navigate replace to={`/settings/${section}${location.search}${location.hash}`}/>;
}
