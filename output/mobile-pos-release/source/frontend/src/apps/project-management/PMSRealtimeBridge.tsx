import { selectedConstruction } from '@/lib/selected-construction';
import { useAuthStore } from '@/store/authStore';
import { useRecordScope } from '@/lib/record-scope';
import { useLocation } from "react-router-dom";
import { usePMSRealtime } from "./realtime";

export default function PMSRealtimeBridge() {
  const location = useLocation();
  useRecordScope();
  const user=useAuthStore(state=>state.user),construction=selectedConstruction(user);
  const path = location.pathname.replace(/\/+$/, "");
  const isPmsRoute = path === "/pms" || path.startsWith("/pms/");
  const ownsWorkspaceFeed = path === "/pms" || path === "/pms/workspaces";
  usePMSRealtime({ enabled: isPmsRoute && !ownsWorkspaceFeed && !construction, showToast: isPmsRoute });
  return null;
}
