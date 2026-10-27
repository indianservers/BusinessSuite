import PeopleDirectoryPage from "@/components/PeopleDirectoryPage";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { workspaceError, type WorkspaceMember } from "./workspaceTypes";
type Team = { id: number; name: string; alias: string; member_ids: number[] };
type Workspace = { id: number; name: string };
const empty = { name: "", alias: "", member_ids: [] as number[] };
function ManageTeamsPage() {
  const [params] = useSearchParams();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState(0);
  const [teams, setTeams] = useState<Team[]>([]);
  const [people, setPeople] = useState<WorkspaceMember[]>([]);
  const [manage, setManage] = useState(false);
  const [draft, setDraft] = useState(empty);
  const [editing, setEditing] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api.get<Workspace[]>("/project-management/workspaces").then(({ data }) => { if (active) { setWorkspaces(data); setSelected(data.find(row => row.id === Number(params.get("workspace")))?.id || data[0]?.id || 0); if (!data.length) setLoading(false); } }).catch(error => { if (active) { setError(workspaceError(error)); setLoading(false); } });
    return () => { active = false; };
  }, [params]);
  useEffect(() => {
    if (!selected) return;
    let active = true; setLoading(true); setManage(false); setTeams([]); setPeople([]); setDraft(empty); setEditing(null); setError(""); setNotice("");
    Promise.all([api.get<{ teams: Team[]; can_manage: boolean }>(`/project-management/workspaces/${selected}/teams`), api.get<WorkspaceMember[]>(`/project-management/workspaces/${selected}/members`)]).then(([library, members]) => {
      if (active) { setTeams(library.data.teams); setManage(library.data.can_manage); setPeople(members.data.filter(member => member.role !== "Guest")); }
    }).catch(error => { if (active) setError(workspaceError(error)); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [selected]);
  const visible = teams.filter(team => `${team.name} ${team.alias}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <div className="mx-auto max-w-5xl space-y-5">
    <header><h1 className="page-title">Teams</h1><Link className="text-sm text-violet-600 hover:underline" to="/pms/analytics/team">Team analytics →</Link><Link className="ml-4 text-sm text-violet-600 hover:underline" to={`/pms/org-chart?workspace=${selected}`}>Organization chart →</Link><p className="page-description">Organize workspace collaborators into named groups. Teams do not change anyone's workspace permissions.</p></header>
    <Link className="text-primary underline" to={`/pms/workspaces?workspace=${selected}`}>Back to workspace</Link>
    <label className="block text-sm">Workspace<select aria-label="Teams workspace" disabled={busy} className="ml-3 rounded-md border bg-background p-2" value={selected} onChange={event => setSelected(Number(event.target.value))}><option value={0} disabled>Choose workspace</option>{workspaces.map(workspace => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>
    {error && <p role="alert" className="text-destructive">{error}</p>}{notice && <p role="status">{notice}</p>}
    {loading ? <p role="status">Loading teams…</p> : !selected ? <p>Create or join a workspace first.</p> : <>
      <Input aria-label="Search teams" placeholder="Search team names or aliases…" value={search} onChange={event => setSearch(event.target.value)} />
      <p className="text-sm text-muted-foreground">{visible.length} teams shown</p>
      {visible.map(team => <article className="flex flex-wrap items-start justify-between gap-3 rounded-lg border p-4" key={team.id}><div><h2 className="font-semibold">{team.name}</h2><p className="text-sm text-muted-foreground">@{team.alias} · {team.member_ids.length} members</p><ul className="mt-2 text-sm">{team.member_ids.map(id => <li key={id}>{people.find(person => person.user_id === id)?.email || `Member ${id}`}</li>)}</ul></div>{manage && <Button variant="outline" disabled={busy} onClick={() => { setEditing(team.id); setDraft({ name: team.name, alias: team.alias, member_ids: [...team.member_ids] }); }}>Edit {team.name}</Button>}</article>)}
      {!visible.length && <p className="rounded border border-dashed p-6">{teams.length ? "No teams match your search." : "No teams in this workspace yet."}</p>}
      {manage && <form className="space-y-4 rounded-lg border p-5" onSubmit={event => {
        event.preventDefault(); if (busy) return; setBusy(true); setError(""); setNotice("");
        const url = `/project-management/workspaces/${selected}/teams${editing ? `/${editing}` : ""}`;
        void (editing ? api.put<Team>(url, draft) : api.post<Team>(url, draft)).then(({ data }) => { setTeams(current => [...current.filter(team => team.id !== data.id), data].sort((a, b) => a.name.localeCompare(b.name))); setDraft(empty); setEditing(null); setNotice("Team saved"); }).catch(error => setError(workspaceError(error))).finally(() => setBusy(false));
      }}><h2 className="font-semibold">{editing ? "Edit team" : "Create team"}</h2><fieldset disabled={busy} className="space-y-3"><label className="block text-sm">Team name<Input required maxLength={120} value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} /></label><label className="block text-sm">Alias<Input required pattern="[a-z0-9]+(-[a-z0-9]+)*" minLength={2} maxLength={60} placeholder="e.g. audit-reviewers" value={draft.alias} onChange={event => setDraft({ ...draft, alias: event.target.value })} /></label><fieldset className="max-h-64 overflow-y-auto rounded border p-3"><legend>Members</legend>{people.map(person => <label className="flex min-h-10 items-center gap-2 text-sm" key={person.id}><input type="checkbox" checked={draft.member_ids.includes(person.user_id)} onChange={event => setDraft({ ...draft, member_ids: event.target.checked ? [...draft.member_ids, person.user_id] : draft.member_ids.filter(id => id !== person.user_id) })} />{person.email}</label>)}</fieldset><div className="flex gap-2"><Button disabled={busy}>{busy ? "Saving…" : "Save team"}</Button>{editing && <Button type="button" variant="outline" onClick={() => { setDraft(empty); setEditing(null); }}>Cancel edit</Button>}</div></fieldset></form>}
    </>}
  </div>;
}

export default function TeamsPage() { return new URLSearchParams(window.location.search).get("manage") === "1" ? <ManageTeamsPage /> : <PeopleDirectoryPage />; }
