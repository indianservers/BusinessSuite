import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { workspaceError } from "../pages/workspaceTypes";

type Invitation = { id: number; workspace: string; role: string; expires_at: string };
export default function InvitationInbox() {
  const [items, setItems] = useState<Invitation[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    const load = () => api.get<Invitation[]>("/project-management/workspace-invitations/mine")
      .then(r => { if (active) { setItems(r.data); setError(""); } }).catch(() => { /* The bell remains available if this optional summary cannot load. */ });
    void load();
    window.addEventListener("focus", load);
    return () => { active = false; window.removeEventListener("focus", load); };
  }, []);
  if (!items.length) return null;
  return <section aria-label="Invitations for you" className="my-4 space-y-3 rounded-xl border border-violet-200 bg-violet-50 p-4 text-slate-900">
    <h2 className="font-semibold">You’re invited · {items.length}</h2>
    {error && <p role="alert">{error}</p>}
    {items.map(i => <div className="flex flex-wrap items-center justify-between gap-3" key={i.id}>
      <div><strong>{i.workspace}</strong><p className="text-sm">Join as {i.role} · Expires {new Date(i.expires_at + (i.expires_at.endsWith("Z") ? "" : "Z")).toLocaleDateString()}</p></div>
      <Button disabled={busy} onClick={async () => {
        setBusy(true); setError("");
        try { const { data } = await api.post(`/project-management/workspace-invitations/${i.id}/accept`); setItems(items => items.filter(item => item.id !== i.id)); navigate(`/pms/workspaces?workspace=${data.workspace_id}`); }
        catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
      }}>Accept invitation</Button>
    </div>)}
  </section>;
}
