import { useSearchParams } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import ProductivityWorkspace from "@/shared/productivity/ProductivityWorkspace";

export default function CRMActivitiesWorkspace() {
  const user = useAuthStore(state => state.user);
  const [params, setParams] = useSearchParams();
  const kind = params.get("workspaceView") === "notes" ? "note" : "task";
  const storageKey = `productivity:crm:${user?.id ?? "anonymous"}:v1`;
  return <ProductivityWorkspace key={storageKey} storageKey={storageKey} initialKind={kind} onKindChange={next => { const query = new URLSearchParams(params); query.set("operation", "/crm/tasks"); query.set("workspaceView", next === "note" ? "notes" : "tasks"); setParams(query, { replace: true }); }}/>;
}
