import { useLocation } from "react-router-dom";
import { usePMSRealtime } from "./realtime";

export default function PMSRealtimeBridge() {
  const location = useLocation();
  const path = location.pathname.replace(/\/+$/, "");
  const isPmsRoute = path === "/pms" || path.startsWith("/pms/");
  const ownsWorkspaceFeed = path === "/pms" || path === "/pms/workspaces";
  usePMSRealtime({ enabled: isPmsRoute && !ownsWorkspaceFeed, showToast: isPmsRoute });
  return null;
}
