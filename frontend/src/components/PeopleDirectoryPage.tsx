import ProfileListCard, { ProfileAction } from "./ProfileListCard";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useRefreshableEffect } from "@/lib/page-refresh";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/store/authStore";

type Person = { id: number; email: string; name: string; role: string; is_active: boolean; workspace_ids: number[]; profile_photo_url?: string | null };
type Group = { id: number; name: string };
type Team = Group & { workspace_id: number; member_ids: number[] };
type Directory = { items: Person[]; total: number; workspaces: Group[]; teams: Team[] };
export default function PeopleDirectoryPage() {
  const userId = useAuthStore(s => s.user?.id);
  const viewKey = `people-directory-views:${userId}`;
  type SavedView = { name: string; query: string; workspace: string; team: string; role: string };
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => { try { const value = JSON.parse(localStorage.getItem(viewKey) || "[]"); return Array.isArray(value) ? value.filter(v => typeof v.name === "string") : []; } catch { return []; } });
  const [viewName, setViewName] = useState("");
  const [viewMessage, setViewMessage] = useState("");
  const [data, setData] = useState<Directory>();
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [team, setTeam] = useState("");
  const [role, setRole] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [selectedPerson, setSelectedPerson] = useState<Person | null>(null);
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
      <div className="space-y-2 rounded-lg border p-3"><div className="flex flex-wrap items-center gap-2"><label className="text-sm">Load saved directory view<select className="ml-2 rounded border bg-background p-2" value="" onChange={e => { const view = savedViews.find(v => v.name === e.target.value); if (view) { setQuery(view.query); setWorkspace(view.workspace); setTeam(view.team); setRole(view.role); } }}><option value="">Choose a saved view</option>{savedViews.map(v => <option key={v.name}>{v.name}</option>)}</select></label><form className="flex flex-wrap gap-2" onSubmit={e => { e.preventDefault(); const next = [...savedViews.filter(v => v.name !== viewName.trim()), { name: viewName.trim(), query, workspace, team, role }].slice(-20); try { localStorage.setItem(viewKey, JSON.stringify(next)); setSavedViews(next); setViewName(""); setViewMessage("Directory view saved on this browser."); } catch { setViewMessage("This browser could not save the view. Your filters are unchanged."); } }}><Input aria-label="Directory view name" placeholder="Save current filters as…" required maxLength={60} value={viewName} onChange={e => setViewName(e.target.value)} /><Button variant="outline" disabled={!viewName.trim()}>Save directory view</Button></form></div>{viewMessage && <p role="status" className="text-xs text-muted-foreground">{viewMessage}</p>}{savedViews.length > 0 && <details><summary className="cursor-pointer text-xs">Manage saved views</summary>{savedViews.map(v => <div key={v.name} className="mt-2 flex gap-3 text-sm"><span>{v.name}</span><button className="underline" onClick={() => { const next = savedViews.filter(item => item.name !== v.name); try { localStorage.setItem(viewKey, JSON.stringify(next)); setSavedViews(next); } catch { setViewMessage("Could not remove saved view."); } }}>Remove</button></div>)}</details>}</div>
      <div className="grid gap-2.5 lg:grid-cols-2 xl:grid-cols-3">{people.map(p => {
        const workspaces = p.workspace_ids.map(id => ({ id, name: data.workspaces.find(w => w.id === id)?.name })).filter(w => !!w.name);
        const memberTeams = data.teams.filter(t => t.member_ids.includes(p.id));
        return <ProfileListCard key={p.id} name={p.name} photoUrl={p.profile_photo_url}
          location={workspaces[0]?.name} subtitle={<><strong>{p.role.replace(/_/g, " ")}</strong> · {p.email}</>}
          status={{ label: p.is_active ? "Active" : "Inactive", tone: p.is_active ? "positive" : "muted" }}
          onOpen={() => setSelectedPerson(p)}
          tags={[
            ...workspaces.slice(0, 2).map(w => ({ label: w.name!, onClick: () => { setWorkspace(String(w.id)); setTeam(""); } })),
            ...memberTeams.slice(0, 2).map(t => ({ label: t.name, onClick: () => { setWorkspace(String(t.workspace_id)); setTeam(String(t.id)); } })),
            ...(workspaces.length + memberTeams.length > 4 ? [{ label: "More memberships", onClick: () => setSelectedPerson(p) }] : []),
          ]}
          actions={<><ProfileAction onClick={() => setSelectedPerson(p)} label={`View profile of ${p.name}`}>View profile</ProfileAction><ProfileAction href={`mailto:${p.email}`} label={`Email ${p.name}`}>Email</ProfileAction></>} />;
      })}</div>
      <Dialog open={!!selectedPerson} onOpenChange={open => { if (!open) setSelectedPerson(null); }}><DialogContent>
        <DialogTitle>Profile overview</DialogTitle>
        {selectedPerson && <><ProfileListCard name={selectedPerson.name} photoUrl={selectedPerson.profile_photo_url}
          subtitle={selectedPerson.role.replace(/_/g, " ")} status={{label:selectedPerson.is_active ? "Active" : "Inactive",tone:selectedPerson.is_active ? "positive" : "muted"}}
          actions={<ProfileAction href={`mailto:${selectedPerson.email}`}>Email {selectedPerson.name}</ProfileAction>} />
          <p className="break-all text-sm text-muted-foreground">{selectedPerson.email}</p>
          <div><h3 className="mb-2 text-sm font-medium">Workspaces &amp; teams</h3><div className="flex flex-wrap gap-2">
            {selectedPerson.workspace_ids.map(id => <ProfileAction key={id} onClick={() => {setWorkspace(String(id));setTeam("");setSelectedPerson(null);}}>{data.workspaces.find(w => w.id === id)?.name || "Workspace"}</ProfileAction>)}
            {data.teams.filter(t => t.member_ids.includes(selectedPerson.id)).map(t => <ProfileAction key={`team-${t.id}`} onClick={() => {setWorkspace(String(t.workspace_id));setTeam(String(t.id));setSelectedPerson(null);}}>{t.name}</ProfileAction>)}
            {!selectedPerson.workspace_ids.length && <p className="text-sm text-muted-foreground">No workspace membership</p>}
          </div></div></>}
      </DialogContent></Dialog>
      {!people.length && <p>No users match these filters.</p>}
    </>}
  </main>;
}
