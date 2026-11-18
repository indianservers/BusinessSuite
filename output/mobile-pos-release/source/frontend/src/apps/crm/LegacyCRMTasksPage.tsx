import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import CRMTasksWorkspace from "./CRMTasksWorkspace";

/** Keep existing CRM records available while new work uses the shared task engine. */
export default function LegacyCRMTasksPage() {
  const user = useAuthStore(state => state.user);
  const navigate = useNavigate();
  return <CRMTasksWorkspace legacyKey={`productivity:crm:${user?.id ?? "anonymous"}:v1`} onNotes={() => navigate("/pms/notes")} />;
}
