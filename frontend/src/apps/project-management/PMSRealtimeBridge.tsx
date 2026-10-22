import { useLocation } from "react-router-dom";
import { usePMSRealtime } from "./realtime";

export default function PMSRealtimeBridge() {
  const location = useLocation();
  const isPmsRoute = location.pathname.startsWith("/pms");
  usePMSRealtime({ enabled: isPmsRoute && location.pathname !== "/pms/workspaces", showToast: isPmsRoute });
  return null;
}
