import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import { workspaceError } from "../pages/workspaceTypes";
import AddExistingPeopleDialog from "./people/AddExistingPeopleDialog";
import { ManagePersonButton, PersonIdentity } from "./people/PersonIdentity";
import { peopleBase } from "./people/peopleTypes";
import "./assignee-picker.css";

type Person = { id: number; email: string; name?: string; photo_url?: string | null; role?: string; availability?: string };
export default function AssigneePicker({ people, value, onChange, disabled = false, label = "Task assignees", projectId, single = false, onDate }: {
  people: Person[]; value: number[]; onChange: (ids: number[]) => void | Promise<unknown>; disabled?: boolean; label?: string; projectId?: number; single?: boolean; onDate?: string;
}) {
  const detailsRef=useRef<HTMLDetailsElement>(null);
  const route = useParams();
  const pid = projectId || Number(route.projectId);
  const [busy, setBusy] = useState(false);
  const [opened, setOpened] = useState(false);
  const [adding, setAdding] = useState(false);
  const [warnings,setWarnings]=useState<string[]>([]);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [options, setOptions] = useState<Person[]>(people);
  const [canAdd, setCanAdd] = useState(false);
  const [workspaceId, setWorkspaceId] = useState<number>();
  const [unavailable, setUnavailable] = useState("Choose a project to add people while assigning work.");
  useEffect(() => setOptions(people), [people]);
  const load = useCallback(async () => {
    if (!pid) return;
    const { data } = await api.get<{ items: Person[]; workspace_id?: number; can_add_existing: boolean; unavailable_reason: string }>(`${peopleBase}/assignment-options`, { params: { project_id: pid } });
    setOptions(data.items); setCanAdd(data.can_add_existing); setWorkspaceId(data.workspace_id); setUnavailable(data.unavailable_reason);
  }, [pid]);
  useEffect(() => { if (opened) void load().catch(e => setError(workspaceError(e))); }, [opened, load]);
  useEffect(()=>{let active=true;if(opened&&pid&&value.length)void Promise.all(value.map(id=>api.get<{warnings:string[]}>("/project-management/management/assignment-warnings",{params:{project_id:pid,user_id:id,on:onDate||undefined}}))).then(results=>{if(active)setWarnings([...new Set(results.flatMap(r=>r.data.warnings))]);}).catch(()=>{});return()=>{active=false;};},[opened,pid,value.join(","),onDate]);
  const names = value.map(id => options.find(p => p.id === id)?.name || people.find(p => p.id === id)?.email || `Member ${id}`);
  async function change(ids: number[]) {
    setBusy(true); setError("");
    try { if(pid){const checks=await Promise.all(ids.filter(id=>!value.includes(id)).map(id=>api.get<{warnings:string[]}>("/project-management/management/assignment-warnings",{params:{project_id:pid,user_id:id,on:onDate||undefined}})));setWarnings(checks.flatMap(r=>r.data.warnings));} await onChange(single?ids.slice(-1):ids); if(single&&detailsRef.current)detailsRef.current.open=false; } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
  }
  return <><details ref={detailsRef} className="pms-assignee-picker" onToggle={e => setOpened(e.currentTarget.open)}><summary aria-label={label}>{names.length ? names.join(", ") : "Unassigned"}</summary>
    <fieldset disabled={disabled || busy} aria-label={label}>
      <legend>{disabled ? "Assigned collaborators" : "Select one or more people"}</legend>
      <input aria-label="Search assignees" placeholder="Find a name, email or role…" value={search} onChange={e => setSearch(e.target.value)} />
      {error && <p role="alert">{error}</p>}{warnings.map((w,i)=><p role="status" className="text-xs text-amber-700" key={i}>{w}</p>)}
      {options.filter(p => `${p.email} ${p.name || ""} ${p.role || ""}`.toLowerCase().includes(search.toLowerCase())).map(p => <div key={p.id} className="flex items-start gap-2 border-b py-2"><input aria-label={`Assign ${p.email}`} type="checkbox" checked={value.includes(p.id)} onChange={e => { void change(e.target.checked ? [...value, p.id] : value.filter(id => id !== p.id)); }} /><div className="min-w-0 flex-1"><PersonIdentity person={p} /><ManagePersonButton userId={p.id} projectId={pid || undefined} workspaceId={workspaceId} /></div></div>)}
      {!options.length && <p>No eligible collaborators yet. Authorized administrators can add an existing person below.</p>}
      {!disabled && <><button type="button" disabled={!canAdd || !pid} onClick={() => setAdding(true)}>Add existing person</button>{!canAdd && <p className="text-xs">{unavailable}</p>}</>}
      {!!value.length && !disabled && <button type="button" onClick={() => { void change([]); }}>Clear assignees</button>}
      {busy && <p role="status">Saving assignees…</p>}
    </fieldset>
  </details><AddExistingPeopleDialog open={adding} onClose={() => setAdding(false)} projectId={pid || undefined} onAdded={async ids => { await load(); await change([...new Set([...value, ...ids])]); }} /></>;
}
