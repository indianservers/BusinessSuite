import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, recruitmentApi } from "@/services/api";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { WorkflowRecord } from "./model";

type Destination = { target: string; approval_required?: boolean; orderAction?: "submit" | "confirm" };
/** Server-provided destinations only. Mutations retain all domain validation. */
export function WorkflowStageReview({ module, record, close, saved }: { module: "hrms" | "pms" | "srm"; record: WorkflowRecord; close: () => void; saved: () => void }) {
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const choices = useQuery({
    queryKey: ["dashboard-workflow-transitions", module, record.id, record.jobId], retry: false,
    queryFn: async ({ signal }): Promise<Destination[]> => {
      if (module === "srm") {
        const { data } = await api.get<{ status: string; metadata_json?: { source?: string } }>(`/srm/sales-orders/${record.id}`, { signal, recordCache: false });
        if (data.metadata_json?.source === "pos") return [];
        return data.status === "draft" ? [{ target: "Submit for approval", orderAction: "submit" }] : data.status === "approved" ? [{ target: "Confirm order", orderAction: "confirm" }] : [];
      }
      if (module === "pms") {
        const { data } = await api.get<{ can_request: boolean; transitions: Destination[] }>(`/project-management/tasks/${record.id}/transition-approvals`, { signal, recordCache: false });
        return data.can_request ? data.transitions : [];
      }
      const { data } = await api.get<{ stages: { name: string }[] }>(`/pipeline-workspaces/hrms/jobs/${record.jobId}/configuration`, { signal, recordCache: false });
      return data.stages.map(s => ({ target: s.name }));
    },
  });
  const destination = choices.data?.find(d => d.target === target);
  async function apply() {
    if (busy || !destination) return;
    setBusy(true); setError("");
    try {
      if (module === "srm" && destination.orderAction) await api.post(`/srm/sales-orders/${record.id}/${destination.orderAction}`);
      else if (module === "hrms") await recruitmentApi.updateCandidateStatus(Number(record.id), target);
      else if (destination.approval_required) await api.post(`/project-management/tasks/${record.id}/transition-approvals`, { target });
      else await api.patch(`/project-management/tasks/${record.id}`, { status: target });
      saved(); close();
    } catch (e) {
      const detail = (e as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
      setError(typeof detail === "string" ? detail : "This transition could not be applied. Open the record to review its requirements.");
    } finally { setBusy(false); }
  }
  return <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent><DialogTitle>Review stage change</DialogTitle><DialogDescription>{record.title} · Current stage: {record.stageId}. Required fields, capacity, permissions and approvals are checked before any change.</DialogDescription>
    {choices.isPending ? <p role="status">Loading permitted destinations…</p> : choices.isError ? <p role="alert">Stage rules could not be loaded. Open the record to review its workflow.</p> : <form className="grid gap-3" onSubmit={e => { e.preventDefault(); void apply(); }}>
      <label className="grid gap-1 text-sm">Destination stage<select aria-label="Destination stage" className="rounded border bg-background p-2" value={target} onChange={e => setTarget(e.target.value)} disabled={busy}><option value="">Choose a destination</option>{choices.data?.filter(d => d.target !== record.stageId).map(d => <option key={d.target} value={d.target}>{d.target}{d.approval_required ? " · approval required" : ""}</option>)}</select></label>
      {destination?.approval_required && <p className="text-sm">This submits a transition approval request. The task stays in its current stage until approval is completed and applied.</p>}
      {module === "hrms" && <p className="text-xs text-muted-foreground">Changing hiring stage does not issue an offer or create an employee.</p>}
      {module === "srm" && <p className="text-xs text-muted-foreground">Submission follows the order's approval threshold. The document workflow determines the resulting status; confirmation requires an approved order.</p>}
      {error && <p role="alert" className="text-destructive">{error} Your selection is retained.</p>}
      <Button type="submit" disabled={busy || !destination}>{busy ? "Saving…" : destination?.approval_required ? "Request transition approval" : "Confirm stage change"}</Button>
    </form>}
    <Link className="text-sm text-primary underline" to={record.href}>Open full record and workflow</Link>
  </DialogContent></Dialog>;
}
