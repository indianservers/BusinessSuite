import { useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { workspaceError } from "../pages/workspaceTypes";

export default function WorkflowFeedPanel({ workspaceId }: { workspaceId: number }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [events, setEvents] = useState<{ event_id: string; type: string; task: { title: string } | null }[] | null>(null);
  const endpoint = `${window.location.origin}/api/v1/project-management/workspaces/${workspaceId}/workflow-events`;
  return <section className="space-y-3 rounded border p-4" aria-label="n8n workflow preparation"><h2 className="text-lg font-semibold">n8n workflows · Prepared</h2><p>Not connected. A read-only event feed is available to workspace owners and admins. No events are sent to an external service.</p><label className="block">Event feed URL<input readOnly aria-label="Workflow event feed URL" className="mt-1 w-full rounded border bg-background p-3 text-sm" value={endpoint} onFocus={event => event.target.select()} /></label><p className="text-sm text-muted-foreground">The integration will need authentication, a saved cursor and event-ID deduplication. The repository includes an inactive n8n starter and setup instructions.</p><Button variant="outline" disabled={busy} onClick={async () => { setBusy(true); setError(""); try { const { data } = await api.get<{ items: typeof events }>(`/project-management/workspaces/${workspaceId}/workflow-events`, { params: { limit: 6, replay: false } }); setEvents(data.items); } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); } }}>{busy ? "Loading events…" : "Preview first events"}</Button>{error && <p role="alert" className="text-destructive">{error}</p>}{events && <div aria-live="polite">{!events.length && <p>No task events yet.</p>}{events.map(event => <p key={event.event_id} className="break-words border-b py-2 text-sm"><strong>{event.type}</strong> · {event.task?.title || "Task unavailable"}<small className="block text-muted-foreground">{event.event_id}</small></p>)}</div>}</section>;
}
