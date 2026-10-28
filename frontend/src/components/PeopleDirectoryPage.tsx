import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Person = { id: number; email: string; name: string; role: string; is_active: boolean; workspace_ids: number[] };
type Group = { id: number; name: string };
type Team = Group & { workspace_id: number; member_ids: number[] };
type Directory = { items: Person[]; total: number; workspaces: Group[]; teams: Team[] };
export default function PeopleDirectoryPage() {
  const [data, setData] = useState<Directory>();
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [team, setTeam] = useState("");
  const [role, setRole] = useState("");
  const [attempt, setAttempt] = useState(0);
  useRefreshableEffect(() => {
    let cancelled = false;
    setData(undefined); setError("");
    async function load() {
      const first = (await api.get<Directory>("/users/directory", { params: { page: 1, page_size: 200 } })).data;
      const items = [...first.items];
      for (let page = 2; items.length < first.total; page++) {
        if (cancelled) return;
        const next = (await api.get<Directory>("/users/directory", { params: { page, page_size: 200 } })).data;
        if (!next.items.length) break;
        items.push(...next.items);
      }
      if (!cancelled) setData({ ...first, items });
    }
    void load().catch(e => { if (!cancelled) setError(e.response?.data?.detail || "Unable to load people. Please retry."); });
    return () => { cancelled = true; };
  }, [attempt]);
  const teams = data?.teams.filter(t => !workspace || t.workspace_id === Number(workspace)) || [];
  const people = useMemo(() => data?.items.filter(p =>
    (!query || `${p.name} ${p.email}`.toLowerCase().includes(query.toLowerCase())) &&
    (!workspace || p.workspace_ids.includes(Number(workspace))) &&
    (!team || data.teams.find(t => t.id === Number(team))?.member_ids.includes(p.id)) &&
    (!role || p.role === role)) || [], [data, query, workspace, team, role]);
  return <main className="mx-auto w-full max-w-7xl space-y-5 p-4 md:p-8">
    <div><h1 className="text-2xl font-semibold">People directory</h1><p className="text-muted-foreground">Explore registered users across all workspaces available to your account, including people without a workspace.</p></div>
    <div className="flex flex-wrap gap-3"><Link to="/pms">Workspaces</Link><Link to="/pms/teams?manage=1">Manage workspace teams</Link></div>
    {error ? <div role="alert">{error} <Button onClick={() => setAttempt(a => a + 1)}>Retry</Button></div> : !data ? <p role="status">Loading people…</p> : <>
      <div className="flex flex-wrap gap-3">
        <Input className="max-w-sm" aria-label="Search people" placeholder="Search name or email" value={query} onChange={e => setQuery(e.target.value)} />
        <select className="rounded border p-2" aria-label="Workspace filter" value={workspace} onChange={e => { setWorkspace(e.target.value); setTeam(""); }}><option value="">All workspaces</option>{data.workspaces.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
        <select className="rounded border p-2" aria-label="Team filter" value={team} onChange={e => setTeam(e.target.value)}><option value="">All teams</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name} · {data.workspaces.find(w => w.id === t.workspace_id)?.name}</option>)}</select>
        <select className="rounded border p-2" aria-label="Role filter" value={role} onChange={e => setRole(e.target.value)}><option value="">All roles</option>{[...new Set(data.items.map(p => p.role))].sort().map(r => <option key={r}>{r}</option>)}</select>
        <Button variant="outline" onClick={() => { setQuery(""); setWorkspace(""); setTeam(""); setRole(""); }}>Clear filters</Button>
      </div>
      <p role="status">{people.length} of {data.total} users</p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{people.map(p => <article data-context-record={p.name} key={p.id} className="space-y-2 rounded-xl border bg-card p-5"><h2 className="font-semibold">{p.name}</h2><a data-context-action={`Email ${p.name}`} className="break-all text-primary" href={`mailto:${p.email}`}>{p.email}</a><p className="text-sm">{p.role} · {p.is_active ? "Active" : "Inactive"}</p><div className="flex flex-wrap gap-2">{p.workspace_ids.map(id => <button data-context-action={`Explore workspace ${data.workspaces.find(w => w.id === id)?.name}`} className="rounded border px-2 py-1 text-sm" key={id} onClick={() => { setWorkspace(String(id)); setTeam(""); }}>{data.workspaces.find(w => w.id === id)?.name}</button>)}{!p.workspace_ids.length && <span className="text-sm text-muted-foreground">No workspace membership</span>}</div><div className="flex flex-wrap gap-2">{data.teams.filter(t => t.member_ids.includes(p.id)).map(t => <button data-context-action={`Explore team ${t.name}`} className="rounded bg-muted px-2 py-1 text-sm" key={t.id} onClick={() => { setWorkspace(String(t.workspace_id)); setTeam(String(t.id)); }}>{t.name}</button>)}</div></article>)}</div>
      {!people.length && <p>No users match these filters.</p>}
    </>}
  </main>;
}
