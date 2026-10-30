import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError } from "../../pages/workspaceTypes";
import { peopleBase, peopleChanged, openPerson, type Destinations, type Person } from "./peopleTypes";
import { PersonIdentity } from "./PersonIdentity";

export default function AddExistingPeopleDialog({ open, onClose, workspaceId, projectId, personIds = [], onAdded }: { open: boolean; onClose: () => void; workspaceId?: number; projectId?: number; personIds?: number[]; onAdded?: (ids: number[]) => void | Promise<void> }) {
  const [options, setOptions] = useState<Destinations>();
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [workspaces, setWorkspaces] = useState<number[]>([]);
  const [projects, setProjects] = useState<number[]>([]);
  const [query, setQuery] = useState("");
  const [reason, setReason] = useState("Add existing people to the delivery team");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState<{ ids: number[]; warnings: string[] }>();
  const personKey = personIds.join(",");
  useEffect(() => {
    if (!open) return;
    let active = true;
    setSaved(undefined); setError(""); setLoading(true); setQuery(""); setSelected(personKey ? personKey.split(",").map(Number) : []);
    setWorkspaces(workspaceId ? [workspaceId] : []); setProjects(projectId ? [projectId] : []);
    void api.get<Destinations>(`${peopleBase}/options`).then(async r => {
      if (!active) return;
      setOptions(r.data);
      const wid = workspaceId || r.data.workspaces[0]?.id;
      const response = await api.get<{ items: Person[] }>(`${peopleBase}/directory`, { params: { status: "active", ...(wid ? { workspace_id: wid } : projectId ? { project_id: projectId } : {}) } });
      if (active) setPeople(response.data.items);
    }).catch(e => { if (active) setError(workspaceError(e)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [open, workspaceId, projectId, personKey]);
  const toggle = (items: number[], id: number) => items.includes(id) ? items.filter(value => value !== id) : [...items, id];
  return <Dialog open={open} onOpenChange={value => { if (!value && !busy) onClose(); }}><DialogContent overlayClassName="z-[110]" className="z-[111] max-h-[90dvh] max-w-3xl overflow-y-auto"><DialogTitle className="text-xl font-semibold">Add existing person</DialogTitle><p className="text-sm text-muted-foreground">Registered people join immediately. Select one or more people and destinations. Selecting a project also creates Member access to its workspace when needed; no invitation approval is required.</p>
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {saved ? <div role="status" className="space-y-3"><h3 className="font-semibold">Memberships saved</h3>{saved.warnings.map((warning, i) => <p className="rounded border border-amber-300 p-3 text-sm" key={i}>{warning}</p>)}<Button disabled={busy} onClick={async () => { setBusy(true); try { await onAdded?.(saved.ids); onClose(); } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); } }}>Done</Button></div> : loading ? <p role="status">Loading eligible people and destinations…</p> : <form className="space-y-4" onSubmit={async e => {
      e.preventDefault(); setBusy(true); setError("");
      try { const { data } = await api.post(`${peopleBase}/memberships/bulk`, { user_ids: selected, workspace_ids: workspaces, project_ids: projects, role: "Member", reason }); peopleChanged(); if (data.warnings?.length) setSaved({ ids: selected, warnings: data.warnings }); else { await onAdded?.(selected); onClose(); } }
      catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
    }}><fieldset disabled={busy} className="space-y-4"><div className="grid gap-4 md:grid-cols-2"><section><h3 className="mb-2 font-semibold">People · {selected.length} selected</h3><Input aria-label="Search existing people" placeholder="Search name, email or role" value={query} onChange={e => setQuery(e.target.value)} /><div className="mt-2 max-h-72 space-y-2 overflow-auto">{people.filter(p => `${p.name} ${p.email} ${p.role}`.toLowerCase().includes(query.toLowerCase())).map(p => <div className="flex items-start gap-2 rounded border p-2" key={p.id}><input className="mt-2 shrink-0" type="checkbox" aria-label={`Select ${p.email}`} checked={selected.includes(p.id)} onChange={() => setSelected(toggle(selected, p.id))} /><div className="min-w-0 flex-1"><PersonIdentity person={p} /><button type="button" className="rounded border px-2 py-1 text-xs" onClick={() => { onClose(); openPerson({ userId: p.id }); }}>Manage person</button></div></div>)}</div></section><section className="space-y-3"><h3 className="font-semibold">Destinations</h3><fieldset className="max-h-40 overflow-auto rounded border p-2"><legend className="text-sm">Workspaces</legend>{options?.workspaces.map(w => <label className="flex items-center gap-2 py-2 text-sm" key={w.id}><input type="checkbox" checked={workspaces.includes(w.id)} onChange={() => setWorkspaces(toggle(workspaces, w.id))} />{w.name}</label>)}</fieldset><fieldset className="max-h-48 overflow-auto rounded border p-2"><legend className="text-sm">Projects</legend>{options?.projects.map(p => <label className="flex items-center gap-2 py-2 text-sm" key={p.id}><input type="checkbox" aria-label={`Select project ${p.name} in ${options?.workspaces.find(w => w.id === p.workspace_id)?.name || "organization"}`} checked={projects.includes(p.id)} onChange={() => setProjects(toggle(projects, p.id))} /><span>{p.name}<small className="block text-muted-foreground">{p.project_key} · {options?.workspaces.find(w => w.id === p.workspace_id)?.name || "Organization project"}</small></span></label>)}</fieldset>{!options?.workspaces.length && !options?.projects.length && <p className="text-sm">No destinations are available in your assigned management scope.</p>}</section></div><label className="block text-sm">Reason<Input required minLength={3} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></label><p className="text-xs text-muted-foreground">Existing memberships are preserved. This action never promotes someone to workspace Admin; only the workspace owner can appoint admins.</p><div className="flex justify-end gap-2"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button disabled={busy || !selected.length || (!projects.length && !workspaces.length)}>{busy ? "Adding people…" : `Add ${selected.length || "selected"} ${selected.length === 1 ? "person" : "people"}`}</Button></div></fieldset></form>}
  </DialogContent></Dialog>;
}
