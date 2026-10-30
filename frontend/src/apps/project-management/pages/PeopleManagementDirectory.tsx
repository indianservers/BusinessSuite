import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ProfileListCard from "@/components/ProfileListCard";
import { usePageRefresh } from "@/lib/page-refresh";
import AddExistingPeopleDialog from "../components/people/AddExistingPeopleDialog";
import { ManagePersonButton } from "../components/people/PersonIdentity";
import { peopleBase, type Person, type Destinations } from "../components/people/peopleTypes";
import { workspaceError } from "./workspaceTypes";

export default function PeopleManagementDirectory() {
  const [data, setData] = useState<{ items: Person[]; counts: Record<string, number>; total: number }>();
  const [options, setOptions] = useState<Destinations>();
  const [status, setStatus] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    const [directory, destinations] = await Promise.all([api.get(`${peopleBase}/directory`, { params: { status } }), api.get<Destinations>(`${peopleBase}/options`)]);
    setData(directory.data); setOptions(destinations.data); setError("");
  }, [status]);
  useEffect(() => { setData(undefined); void load().catch(e => setError(workspaceError(e))); }, [load]);
  useEffect(() => { const changed = () => { void load().catch(e => setError(workspaceError(e))); }; window.addEventListener("pms:people-changed", changed); return () => window.removeEventListener("pms:people-changed", changed); }, [load]);
  usePageRefresh(load);
  const manageable = !!options && !!(options.workspaces.length || options.projects.length);
  const visible = data?.items.filter(p => `${p.name} ${p.email} ${p.role}`.toLowerCase().includes(query.toLowerCase())) || [];
  return <div className="mx-auto max-w-7xl space-y-5"><header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="page-title">People directory</h1><p className="page-description">Find existing people, manage access, and add teams directly within your assigned scope.</p></div><div className="flex flex-wrap gap-2"><Button disabled={!manageable} onClick={() => { setSelected([]); setAdding(true); }}>Add existing person</Button><Button variant="outline" asChild><Link to="/pms/members">Workspace & project members</Link></Button><Link className="self-center text-sm underline" to="/pms/members#invitations">Invite by email</Link></div></header>
    {!manageable && options && <p className="text-sm text-muted-foreground">Adding people requires a workspace administrator or authorized organization Admin/HR role within your assigned scope.</p>}
    <div className="flex flex-wrap gap-2" role="group" aria-label="People status filters">{[["", "All people"], ["active", "Active"], ["suspended", "Suspended"], ["terminated", "Terminated"], ["invited", "Invited"]].map(([key, label]) => <button type="button" className={`rounded-full border px-3 py-2 text-sm ${key === status ? "bg-primary text-primary-foreground" : ""}`} aria-pressed={key === status} key={key} onClick={() => { setStatus(key); setSelected([]); }}>{label}{key && ` · ${data?.counts[key] ?? 0}`}</button>)}</div>
    <div className="flex flex-wrap items-center gap-3"><Input className="max-w-md" aria-label="Search people directory" placeholder="Search name, email or role" value={query} onChange={e => setQuery(e.target.value)} /><span className="text-sm">{visible.length} shown</span>{!!selected.length && <Button disabled={!manageable} onClick={() => setAdding(true)}>Add {selected.length} selected people to destinations</Button>}</div>
    {error && <p role="alert" className="text-destructive">{error}<Button variant="outline" onClick={() => void load().catch(e => setError(workspaceError(e)))}>Retry</Button></p>}
    {!data && !error ? <p role="status">Loading people…</p> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{visible.map(person => <article className="space-y-2 rounded-lg border p-2" key={`${person.status}-${person.id}`}><div className="flex items-center justify-between px-2">{person.status === "active" ? <label className="flex items-center gap-2 text-xs"><input type="checkbox" aria-label={`Select ${person.email}`} checked={selected.includes(person.id)} onChange={e => setSelected(e.target.checked ? [...selected, person.id] : selected.filter(id => id !== person.id))} />Select for bulk addition</label> : <span className="text-xs capitalize">{person.status}</span>}<small className="text-muted-foreground">{person.availability}</small></div><ProfileListCard name={person.name} photoUrl={person.photo_url} subtitle={<>{person.role.replace(/_/g, " ")} · {person.email}</>} status={{ label: person.status, tone: person.status === "active" ? "positive" : "muted" }} actions={person.status === "invited" ? <Link className="text-sm underline" to={`/pms/members?workspace=${person.workspace_id}#invitations`}>View / resend invitation</Link> : <><ManagePersonButton userId={person.id} />{person.status === "active" && <button className="text-xs underline" disabled={!manageable} onClick={() => { setSelected([person.id]); setAdding(true); }}>Add to workspace / project</button>}</>} /></article>)}</div>}
    {data && !visible.length && <p className="text-sm text-muted-foreground">No people match this filter.</p>}
    <AddExistingPeopleDialog open={adding} onClose={() => setAdding(false)} personIds={selected} onAdded={async () => { setSelected([]); await load(); }} />
  </div>;
}
