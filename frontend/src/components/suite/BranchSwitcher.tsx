import { NativeSelect } from "@/components/ui/native-select";
import { Link } from "react-router-dom";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Building2, ChevronDown, Settings2 } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import "./app-bar.css";

type Branch = { id: number; name: string; code: string; can_write: boolean; is_active?: boolean };
type Context = { company_id: number; selected: number | null; all_branches: boolean; manage_access: boolean; branches: Branch[] };

const detail = (error: any) => error?.response?.data?.detail || "Unable to complete this action.";

export default function BranchSwitcher() {
  const user = useAuthStore(s => s.user);
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [pendingSwitch, setPendingSwitch] = useState<string | null>(null);
  const current = useQuery<Context>({ queryKey: ["suite-branch-context", user?.id, user?.access?.companyId], enabled: !!user, queryFn: async () => {
    const {data} = await api.get<Context>("/branches/context", {progress: false});
    if (!data || !Array.isArray(data.branches)) throw new Error("Branch choices are unavailable. Retry loading branches.");
    return data;
  }, retry: false, refetchOnWindowFocus: true });
  const context = current.data;
  const storedBranch = sessionStorage.getItem("suite-branch");
  const staleBranch = !!context && !!storedBranch && storedBranch !== String(context.selected);
  async function switchBranch(value: string) {
    if (!context || value === String(context.selected)) return;
    setPendingSwitch(value);
  }
  async function confirmSwitch() {
    if (!pendingSwitch) return;
    setBusy(true);
    await qc.cancelQueries();
    try {
      const { data: access } = await api.get('/access/me', { headers: { 'X-Suite-Branch': pendingSwitch } });
      if (user) useAuthStore.getState().setUser({ ...user, access });
    } catch (e) { setError(detail(e)); setBusy(false); setPendingSwitch(null); return; }
    sessionStorage.setItem("suite-branch", pendingSwitch);
    // A reload destroys local component state, in-flight requests, sockets, and
    // non-query caches; sessionStorage keeps other tabs independent.
    qc.clear();
    if (canAccessRoute(window.location.pathname, user?.role, user?.is_superuser)) window.location.reload();
    else window.location.assign('/dashboard');
  }
  if (!user) return null;
  return <div className="suite-branch-control">
    <label className="suite-branch-field">
      <Building2 size={16} className="suite-branch-icon" aria-hidden="true" />
      <span className="suite-branch-label">Branch</span>
      <NativeSelect loading={busy || current.isFetching} error={current.isError} aria-label="Current branch" className="suite-branch-select" value={context?.selected ?? ""} disabled={busy || !context || !context.branches.length} onChange={e => void switchBranch(e.target.value)}>
        {!context && <option value="">{current.isError ? "Branch unavailable" : "Loading branches…"}</option>}
        {context && context.selected === null && <option value="">No branch access</option>}
        {context?.branches.map(b => <option key={b.id} value={b.id}>{b.name}{b.is_active === false ? " (archived)" : ""}{b.can_write ? "" : " · read only"}</option>)}
      </NativeSelect>
      <ChevronDown size={14} className="suite-branch-chevron" aria-hidden="true" />
    </label>
    {context?.manage_access && <Link to="/settings/branches" aria-label="Manage branches" title="Manage branches" className="suite-branch-settings"><Settings2 size={16} /></Link>}
    {current.isError && <button className="text-xs text-destructive" onClick={() => { sessionStorage.removeItem("suite-branch"); window.location.reload(); }}>Retry</button>}
    {error && <p role="alert" className="max-w-48 text-xs text-destructive">{error}</p>}
    {staleBranch && <button role="alert" className="max-w-40 text-xs text-destructive" onClick={() => { sessionStorage.removeItem("suite-branch"); qc.clear(); window.location.reload(); }}>Previous branch access changed. Reload available branches.</button>}
    <Dialog.Root open={pendingSwitch !== null} onOpenChange={value => { if (!value) setPendingSwitch(null); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[100] bg-black/50" /><Dialog.Content className="fixed left-1/2 top-1/2 z-[101] w-[min(420px,95vw)] -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-background p-6"><Dialog.Title className="font-semibold">Switch branch?</Dialog.Title><Dialog.Description className="my-3 text-sm text-muted-foreground">Your page will reload in {pendingSwitch === "all" ? "All branches" : context?.branches.find(b => String(b.id) === pendingSwitch)?.name}. Save any unfinished changes before switching.</Dialog.Description><div className="flex justify-end gap-2"><Dialog.Close asChild><Button variant="outline" disabled={busy}>Stay here</Button></Dialog.Close><Button onClick={() => void confirmSwitch()} disabled={busy}>Switch branch</Button></div></Dialog.Content></Dialog.Portal></Dialog.Root>

  </div>;
}
