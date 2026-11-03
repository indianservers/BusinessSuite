import { useRef, useState } from "react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { failure, type Relationship } from "./types";
export default function AudienceBulkFollowUp({ records, close, saved }: { records: Relationship[]; close: () => void; saved: () => void }) {
  const [due, setDue] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [result, setResult] = useState<{ items: { key: string; saved: boolean; message?: string }[]; saved: number }>();
  const request = useRef(crypto.randomUUID());
  return <Dialog open onOpenChange={open => { if (!open && !busy) close(); }}><DialogContent><DialogTitle>Schedule selected relationships</DialogTitle><p className="text-sm">Schedule one follow-up for each of {records.length} explicitly selected relationships. No messages are sent.</p><label className="grid gap-2 text-sm">Next conversation (local time)<input className="rounded border bg-background p-2" type="datetime-local" required value={due} onChange={e => setDue(e.target.value)}/></label>{error && <p role="alert">{error}</p>}{result && <div role="status"><p>{result.saved} of {records.length} follow-ups saved.</p>{result.items.filter(item => !item.saved).map(item => <p key={item.key}>{item.key}: {item.message}</p>)}</div>}<div className="flex justify-end gap-2"><Button variant="outline" disabled={busy} onClick={close}>Close</Button><Button disabled={busy || !due || records.length > 50 || records.some(row => !row.can_edit) || !!result} onClick={async () => { setBusy(true); setError(""); try { const response = await api.post("/crm/growth/follow-ups/bulk", { recipients: records.map(row => ({ entity: row.entity, id: row.id })), action: "schedule", due_at: new Date(due).toISOString(), request_id: request.current }); setResult(response.data); saved(); } catch (e) { setError(failure(e)); } finally { setBusy(false); } }}>{busy ? "Saving…" : "Confirm schedule"}</Button></div></DialogContent></Dialog>;
}
