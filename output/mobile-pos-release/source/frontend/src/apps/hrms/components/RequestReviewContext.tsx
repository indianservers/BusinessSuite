import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { syncScope } from "@/shared/record-sync/store";
export type RequestContext = { employee_id: number; employee_name: string; department: string | null; branch: string | null; manager_name: string | null; approval_path: string[]; routing_note: string; initial_status: string };
export function useRequestContext(kind: "leave" | "expense", employeeId?: number, enabled = true) {
  return useQuery({ queryKey: ["hr-request-context", syncScope(), kind, employeeId], enabled, queryFn: () => api.get<RequestContext>("/employees/workbench/request-context", { params: { kind, employee_id: employeeId } }).then(response => response.data) });
}
export default function RequestReviewContext({ kind, employeeId }: { kind: "leave" | "expense"; employeeId?: number }) {
  const context = useRequestContext(kind, employeeId);
  return <aside className="rounded border bg-muted/30 p-3 text-sm" aria-label="Request approval routing">
    {context.isPending ? <p role="status">Loading employee and approval routing…</p> : context.isError ? <p role="alert">Approval routing could not load. <button type="button" className="underline" onClick={() => void context.refetch()}>Retry</button></p> : <><p><strong>{context.data.employee_name}</strong> · {[context.data.department, context.data.branch].filter(Boolean).join(" · ") || "Organization details not assigned"}</p><p>Review path: {context.data.approval_path.join(" → ")}</p><p className="text-xs text-muted-foreground">{context.data.routing_note}</p></>}
  </aside>;
}
