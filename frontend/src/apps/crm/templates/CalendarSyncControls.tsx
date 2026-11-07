import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";

type SyncStatus = {
  enabled: boolean; importTarget: "crm" | "pms"; lastSyncedAt: string | null;
  nextRunAt: string | null; lastError: string | null; conflicts: number;
  intervalSeconds: number; workerEnabled: boolean;
  counts: { imported?: number; exported?: number };
};
type Conflict = {
  id: number; module: string;
  local: { title?: string; start?: string; end?: string; description?: string; deleted?: boolean };
  remote: { summary?: string; subject?: string; status?: string; isCancelled?: boolean;
    start?: { dateTime?: string; date?: string }; end?: { dateTime?: string; date?: string };
    description?: string; body?: { content?: string }; "@removed"?: unknown };
};

export default function CalendarSyncControls({ connectionId }: { connectionId: number }) {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const base = `/crm/calendar-integrations/${connectionId}`;
  const load = async () => {
    const response = await api.get<SyncStatus>(`${base}/sync`);
    setStatus(response.data);
    if (response.data.conflicts) {
      const rows = await api.get<{ items: Conflict[] }>(`${base}/conflicts`);
      setConflicts(rows.data.items);
    } else setConflicts([]);
  };
  useEffect(() => {
    let active = true;
    const refresh = () => { if (active) void load().catch(() => { if (active) setError("Sync status could not be loaded."); }); };
    refresh();
    const timer = window.setInterval(refresh, 15000);
    return () => { active = false; window.clearInterval(timer); };
  }, [connectionId]);
  const run = async (operation: () => Promise<unknown>) => {
    setBusy(true); setError(""); setMessage("");
    try { await operation(); await load(); }
    catch (e: any) { setError(e?.response?.data?.detail || "Calendar sync could not finish. Please retry."); }
    finally { setBusy(false); }
  };
  const preferences = (enabled: boolean, target: "crm" | "pms") => run(() => api.put(`${base}/sync`, { enabled, import_target: target }));
  if (!status) return <p className="text-sm text-muted-foreground">{error || "Loading sync status…"}</p>;
  return <div className="space-y-3 rounded-md border p-3 text-sm">
    <p>Two-way sync · {status.workerEnabled ? `checks every ${status.intervalSeconds} seconds while the local backend runs` : "background worker disabled"}</p>
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2"><input type="checkbox" checked={status.enabled} disabled={busy}
        onChange={e => void preferences(e.target.checked, status.importTarget)} />Automatic sync</label>
      <label>New external events go to {" "}<select className="rounded border bg-background p-1" value={status.importTarget} disabled={busy}
        onChange={e => void preferences(status.enabled, e.target.value as "crm" | "pms")}>
        <option value="crm">Sales / CRM meetings</option><option value="pms">PMS calendar</option>
      </select></label>
      <Button size="sm" variant="outline" disabled={busy} onClick={() => void run(async () => {
        const result = await api.post(`${base}/sync`);
        setMessage(result.data.skipped ? "Sync is already running. Status will refresh automatically." : `${result.data.imported} imported, ${result.data.exported} exported.`);
      })}>{busy ? "Working…" : "Sync now"}</Button>
    </div>
    <p className="text-muted-foreground">Last sync: {status.lastSyncedAt ? new Date(status.lastSyncedAt).toLocaleString() : "Waiting for first sync"}.
      {status.nextRunAt && ` Next check: ${new Date(status.nextRunAt).toLocaleString()}.`}</p>
    <p className="text-muted-foreground">Exports your Sales/CRM meetings and PMS events. Existing imported events keep their destination. New events are synced within a rolling window of 90 days past and one year ahead.</p>
    {message && <p role="status">{message}</p>}
    {(error || status.lastError) && <p role="alert" className="text-red-600">{error || status.lastError}</p>}
    {conflicts.map(conflict => {
      const remote = conflict.remote;
      const removed = remote?.status === "cancelled" || remote?.isCancelled || remote?.["@removed"];
      return <div key={conflict.id} className="space-y-2 rounded border border-amber-300 p-3">
        <p className="font-medium">Conflicting changes · {conflict.module.toUpperCase()}</p>
        <p>Local: {conflict.local.deleted ? "Deleted" : `${conflict.local.title} · ${conflict.local.start} – ${conflict.local.end}`}</p>
        {conflict.local.description && <p className="whitespace-pre-wrap">{conflict.local.description}</p>}
        <p>Calendar: {removed ? "Deleted" : `${remote?.summary || remote?.subject} · ${remote?.start?.dateTime || remote?.start?.date} – ${remote?.end?.dateTime || remote?.end?.date}`}</p>
        {(remote?.description || remote?.body?.content) && <p className="whitespace-pre-wrap">{remote.description || remote.body?.content}</p>}
        <div className="flex gap-2">{(["local", "remote"] as const).map(keep => <Button key={keep} disabled={busy} size="sm" variant="outline"
          onClick={() => void run(async () => { await api.post(`${base}/conflicts/${conflict.id}`, { keep }); await api.post(`${base}/sync`); })}>
          Keep {keep === "local" ? "local" : "calendar"} version</Button>)}</div>
      </div>;
    })}
  </div>;
}
