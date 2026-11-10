import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { workspaceApiBase, workspaceDataScope, type SavedWorkspace, type WorkspaceModule } from "@/shared/workspace/workspace-management-types";

type Member = { user_id: number; role: string };
export default function EmployeeCRMWorkspaceAccess({ userId }: { userId?: number | null }) {
  return <section className="space-y-4"><h2 className="text-lg font-semibold">Employee workspace access</h2><p className="text-sm text-muted-foreground">Assign the linked login to CRM, HRMS, and PMS workspaces. Module, branch, and record permissions still apply.</p>{!userId ? <p>Link or create a login account first.</p> : (["crm", "hrms", "pms"] as const).map(module => <ModuleWorkspaceAccess key={`${module}:${userId}`} module={module} userId={userId}/>)}</section>;
}
function ModuleWorkspaceAccess({ module, userId }: { module: WorkspaceModule; userId: number }) {
  const actor = useAuthStore(s => s.user), scope = workspaceDataScope(actor), qc = useQueryClient();
  const [selected, setSelected] = useState(""), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const base = workspaceApiBase(module), label = module.toUpperCase(), path = module === "pms" ? "pms" : module;
  const query = useQuery({ queryKey: ["employee-module-workspaces", module, scope, userId], queryFn: async () => {
    const { data } = await api.get<{ items: SavedWorkspace[] }>(base);
    if (module !== "pms") return data.items;
    return Promise.all(data.items.map(async w => {
      const { data: members } = await api.get<Member[]>(`/project-management/workspaces/${w.id}/members`);
      return { ...w, members: members as SavedWorkspace["members"] };
    }));
  }, retry: false, staleTime: 0 });
  const member = (w: SavedWorkspace) => w.owner_id === userId || w.members?.some(m => m.user_id === userId);
  const choices = (query.data || []).filter(w => w.can_manage && w.status === "Active" && !member(w));
  const assign = async () => {
    if (!selected || busy) return;
    setBusy(true); setMessage("");
    try {
      if (module === "pms") await api.post(`/project-management/workspaces/${selected}/members`, { user_id: userId, role: "Member" });
      else {
        const { data: w } = await api.get<SavedWorkspace>(`${base}/${selected}`);
        if (!member(w)) await api.put(`${base}/${selected}`, { name: w.name, description: w.description, icon: w.icon, color: w.color, visibility: w.visibility, views: w.views, status: w.status, expected_status: w.status, expected_version: w.version, members: [...w.members, { user_id: userId, role: "Member" }] });
      }
      setSelected(""); setMessage(`${label} workspace assigned.`);
      await Promise.all([query.refetch(), qc.invalidateQueries({ queryKey: ["managed-workspaces", module] }), qc.invalidateQueries({ queryKey: ["managed-workspace-detail", module] }), qc.invalidateQueries({ queryKey: ["pms-workspace-team"] })]);
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
      setMessage(typeof detail === "string" ? detail : `Could not assign the ${label} workspace. Please retry.`);
    } finally { setBusy(false); }
  };
  return <section aria-label={`${label} workspace access`} className="rounded-lg border p-4 space-y-3"><h3 className="font-semibold">{label} workspace access</h3>
    {query.isPending && <p role="status">Loading {label} workspaces…</p>}
    {query.isError ? <p role="alert">{label} workspaces could not load. Check module access. <Button variant="outline" onClick={() => void query.refetch()}>Retry {label} workspaces</Button></p> : <>
      <ul>{query.data?.filter(member).map(w => <li key={w.id}><Link className="text-primary underline" to={`/${path}/workspaces?space=${w.id}&spaceTab=team`}>{w.name}</Link> · {w.status}</li>)}</ul>
      <label className="block">{label} workspace<select aria-label={`${label} workspace for employee`} className="block rounded border bg-background p-2" value={selected} disabled={busy} onChange={e => setSelected(e.target.value)}><option value="">Select a {label} workspace</option>{choices.map(w => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
      <Button disabled={!selected || busy} onClick={() => void assign()}>{busy ? "Assigning…" : `Assign ${label} workspace`}</Button>
      {query.isSuccess && !choices.length && <p>No additional {label} workspaces are available for you to assign in this branch.</p>}
    </>}
    {message && <p role="status">{message}</p>}<Link className="text-primary underline" to={`/${path}/workspaces`}>Manage {label} workspaces</Link>
  </section>;
}
