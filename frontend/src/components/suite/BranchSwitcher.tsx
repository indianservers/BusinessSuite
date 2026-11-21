import { NativeSelect } from "@/components/ui/native-select";
import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { defaultBranch, saveDefaultBranch } from '@/lib/default-branch';
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Building2, ChevronDown, Settings2, Store, MapPin } from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import { switchSuiteContext } from "@/lib/switch-suite-context";
import "./app-bar.css";
import BusinessPackSwitcher from './BusinessPackSwitcher';

type Branch = { id: number; name: string; code: string; can_write: boolean; is_active?: boolean; company_id?: number; company_name?: string; company_active?: boolean; is_deleted?: boolean };
type Context = { company_id: number; selected: number | null; all_branches: boolean; manage_access: boolean; branches: Branch[]; platform_branches?: Branch[] };

const detail = (error: any) => error?.response?.data?.detail || "Unable to complete this action.";

export default function BranchSwitcher({icon = 'building', showBusinessPack = true}:{icon?:'building'|'store'|'location';showBusinessPack?:boolean} = {}) {
  const BranchIcon=icon==='store'?Store:icon==='location'?MapPin:Building2;
  const user = useAuthStore(s => s.user);
  const qc = useQueryClient();
  const [error, setError] = useState("");
  const [packVisible, setPackVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pendingSwitch, setPendingSwitch] = useState<string | null>(null);
  const [remember, setRemember] = useState(false);
  const autoDefault = useRef(!sessionStorage.getItem('suite-branch') && window.location.pathname !== '/srm/pos/terminal');
  const [, preferenceChanged] = useState(0);
  const current = useQuery<Context>({ queryKey: ["suite-branch-context", user?.id, user?.access?.companyId], enabled: !!user, queryFn: async () => {
    const {data} = await api.get<Context>("/branches/context", {progress: false});
    if (!data || !Array.isArray(data.branches)) throw new Error("Branch choices are unavailable. Retry loading branches.");
    return data;
  }, retry: false, staleTime:60_000, refetchOnWindowFocus: false });
  const context = current.data;
  const choices = user?.is_superuser && context?.platform_branches ? context.platform_branches : context?.branches || [];
  const storedBranch = sessionStorage.getItem("suite-branch");
  const selectedBranch = context?.selected ?? (context?.all_branches ? "all" : "");
  const staleBranch = !!context && !!storedBranch && storedBranch !== String(selectedBranch);
  useEffect(() => {
    if (!context || !autoDefault.current) return;
    autoDefault.current = false;
    const saved = defaultBranch(context.company_id);
    if (!saved || saved === String(selectedBranch) || !context.branches.some(b => String(b.id) === saved && b.can_write && b.is_active !== false && !b.is_deleted)) return;
    void switchSuiteContext(qc, context.company_id, saved).catch(e => setError(detail(e)));
  }, [context, qc, selectedBranch]);
  async function switchBranch(value: string) {
    if (!context || value === String(selectedBranch)) return;
    setPendingSwitch(value);
    setRemember(false);
  }
  async function confirmSwitch() {
    if (!pendingSwitch) return;
    setBusy(true);
    try {
      const company = choices.find(b => String(b.id) === pendingSwitch)?.company_id ?? context?.company_id;
      if (!company) return;
      const switched = await switchSuiteContext(qc, company, pendingSwitch);
      if (switched && remember && pendingSwitch !== 'all') saveDefaultBranch(company, pendingSwitch);
    } catch (e) { setError(detail(e)); setBusy(false); setPendingSwitch(null); return; }
    finally { setBusy(false); }
  }
  if (!user) return null;
  return <div className="suite-branch-control" style={packVisible ? {flexWrap:"wrap"} : undefined}>
    {showBusinessPack && <BusinessPackSwitcher onVisibility={setPackVisible}/>}
    <label className="suite-branch-field">
      <BranchIcon size={icon==='building'?16:20} className="suite-branch-icon" aria-hidden="true" />
      <span className="suite-branch-label">Branch</span>
      <NativeSelect loading={busy || (!context && current.isFetching)} error={current.isError} aria-label="Current branch" className="suite-branch-select" value={selectedBranch} disabled={busy || !context || !choices.length} onChange={e => void switchBranch(e.target.value)}>
        {!context && <option value="">{current.isError ? "Branch unavailable" : "Loading branches…"}</option>}
        {context?.all_branches && <option value="all">{user?.is_superuser ? "All branches · current company" : "All branches"}</option>}
        {context && context.selected === null && !context.all_branches && <option value="">No branch access</option>}
        {choices.map(b => <option key={b.id} value={b.id} disabled={b.company_active === false || b.is_deleted}>{b.company_name ? `${b.company_name} · ` : ""}{b.name}{b.is_deleted ? " (trash)" : b.is_active === false ? " (archived)" : ""}{b.can_write ? "" : " · read only"}</option>)}
      </NativeSelect>
      <ChevronDown size={14} className="suite-branch-chevron" aria-hidden="true" />
    </label>
    {context?.manage_access && <Link to="/settings/branches" aria-label="Manage branches" title="Manage branches" className="suite-branch-settings"><Settings2 size={16} /></Link>}
    {context?.selected && context.branches.some(b => b.id === context.selected && b.can_write && b.is_active !== false) && defaultBranch(context.company_id) !== String(context.selected) && <button className="text-xs" onClick={() => {
      try { saveDefaultBranch(context.company_id, String(context.selected)); preferenceChanged(value => value + 1); }
      catch { setError('The default branch could not be saved in this browser.'); }
    }}>Set as default branch</button>}
    {current.isError && <button className="text-xs text-destructive" onClick={() => { sessionStorage.removeItem("suite-branch"); window.location.reload(); }}>Retry</button>}
    {error && <p role="alert" className="max-w-48 text-xs text-destructive">{error}</p>}
    {staleBranch && <button role="alert" className="max-w-40 text-xs text-destructive" onClick={() => { sessionStorage.removeItem("suite-branch"); qc.clear(); window.location.reload(); }}>Previous branch access changed. Reload available branches.</button>}
    <Dialog.Root open={pendingSwitch !== null} onOpenChange={value => { if (!value) setPendingSwitch(null); }}><Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[100] bg-black/50" /><Dialog.Content className="fixed left-1/2 top-1/2 z-[101] w-[min(420px,95vw)] -translate-x-1/2 -translate-y-1/2 rounded-xl border bg-background p-6"><Dialog.Title className="font-semibold">Switch branch?</Dialog.Title><Dialog.Description className="my-3 text-sm text-muted-foreground">Your page will reload in {pendingSwitch === "all" ? "All branches" : choices.find(b => String(b.id) === pendingSwitch)?.name}. Save any unfinished changes before switching.</Dialog.Description>{pendingSwitch !== "all" && <label className="mb-4 flex items-center gap-2 text-sm"><input type="checkbox" checked={remember} onChange={event => setRemember(event.target.checked)}/>Set as my default branch in this browser</label>}<div className="flex justify-end gap-2"><Dialog.Close asChild><Button variant="outline" disabled={busy}>Stay here</Button></Dialog.Close><Button onClick={() => void confirmSwitch()} disabled={busy}>Switch branch</Button></div></Dialog.Content></Dialog.Portal></Dialog.Root>

  </div>;
}
