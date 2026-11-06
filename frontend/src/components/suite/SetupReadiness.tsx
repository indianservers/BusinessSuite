import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import SetupGuide from "./SetupGuide";
import { Button } from "@/components/ui/button";
import { ListChecks } from "lucide-react";

export type Item = {id: string; title: string; description: string; ready: boolean; destination: string; canRepair: boolean; module?: string; required?: boolean};
type Readiness = {companyId: number; ready: boolean; items: Item[]; moduleItems?: Item[]; recommendations?: Item[]};

export default function SetupReadiness({embedded = false, navigation = false, collapsed = false, onNavigate}: {embedded?: boolean; navigation?: boolean; collapsed?: boolean; onNavigate?:()=>void}) {
  const {user, isAuthenticated} = useAuthStore();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  const company = sessionStorage.getItem("suite-organization") || user?.access?.companyId;
  const enabled = isAuthenticated && !/^\/(platform\/|login|f\/|forms\/communication\/|portal\/|invite-access|reset-password)/.test(location.pathname);
  const query = useQuery({queryKey: ["company-setup", user?.id, company, location.pathname], enabled,
    queryFn: async () => {
      const {data} = await api.get<Readiness>("/access/setup", {progress:false, recordCache:false});
      if (!Array.isArray(data?.items) || typeof data.ready !== "boolean") throw new Error("Setup status unavailable");
      return data;
    }, retry:false, staleTime:0, refetchOnWindowFocus:true, refetchInterval:60000});
  useEffect(() => {
    if (navigation) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => { clearTimeout(timer); timer = setTimeout(() => void query.refetch(), 250); };
    const required = () => {refresh(); setOpen(true);};
    window.addEventListener("suite:record-mutated", refresh);
    window.addEventListener("suite:setup-required", required);
    return () => {clearTimeout(timer); window.removeEventListener("suite:record-mutated",refresh); window.removeEventListener("suite:setup-required",required);};
  }, [query.refetch, embedded, navigation]);
  useEffect(() => {setOpen(false);}, [company, location.pathname]);
  const pageItems = [...(query.data?.items || []), ...(query.data?.moduleItems || [])]
    .filter(item => item.required !== false && !item.ready && location.pathname.replace(/\/$/, "") === item.destination);
  const guidePath = location.pathname === "/pms/reports" && new URLSearchParams(location.search).get("operation") === "/pms/dashboards" ? "/pms/dashboards" : location.pathname.replace(/\/$/, "");
  const guideModule = ({"/hrms":"hrms", "/hrms/dashboard":"hrms", "/hrms/manager-dashboard":"hrms", "/fam":"fam", "/fam/dashboard":"fam", "/crm":"crm", "/crm/dashboard":"crm", "/crm/sales-home":"crm", "/srm":"srm", "/srm/dashboard":"srm", "/pms":"project_management", "/pms/overview":"project_management", "/pms/dashboards":"project_management"} as Record<string,string>)[guidePath];
  const showGuide = ["/settings", "/setup-guide"].includes(location.pathname) || !!guideModule || ["/pms/workspaces", "/pms/projects", "/pms/tasks"].includes(guidePath);
  const scopedModule = guideModule || (guidePath.startsWith("/pms/") ? "project_management" : undefined);
  if (navigation) {
    const remaining = [...(query.data?.items || []), ...(query.data?.moduleItems || [])].filter(i=>i.required!==false && !i.ready).length;
    return enabled && remaining > 0 ? <Link to="/setup-guide" title="Setup guide" onClick={onNavigate} className={`nav-link mx-2 mt-2 flex items-center gap-2 ${location.pathname === "/setup-guide" ? "nav-link-active" : "nav-link-inactive"} ${collapsed ? "justify-center" : ""}`}><ListChecks size={18}/>{!collapsed && <><span className="flex-1">Setup guide</span><span className="rounded-full bg-primary/15 px-2 text-xs">{remaining}</span></>}</Link> : null;
  }
  if (!enabled || (!embedded && (query.isPending || (query.data?.ready && !open && !pageItems.length)))) return null;
  if (embedded) return showGuide ? <SetupGuide data={query.data} module={scopedModule} loading={query.isPending} error={query.isError} refreshing={query.isFetching} refresh={()=>void query.refetch()}/> : null;
  const missing = query.data?.items.filter(i => i.required !== false && !i.ready) || [];
  const moduleMissing = query.data?.moduleItems?.filter(i => i.required !== false && !i.ready) || [];
  const renderItem = (item: Item) => <li key={item.id} className="rounded-lg border p-3">
    <strong>{item.title} <span className="text-destructive" aria-label="mandatory">*</span></strong><p className="mb-2 text-sm text-muted-foreground">{item.description}</p>
    {item.canRepair ? <Link className="text-sm font-medium underline" to={item.destination} onClick={()=>setOpen(false)}>Add or repair {item.title.toLowerCase()}</Link> : <p className="text-sm">Ask your company administrator to complete this item.</p>}
  </li>;
  return <>
    {!!pageItems.length && <section aria-label="Mandatory setup requirements" className="mx-4 my-3 rounded-lg border border-amber-500/40 bg-background p-4 text-sm">
      <p className="font-semibold"><span className="text-destructive">*</span> Mandatory setup</p>
      <p className="mt-1 text-muted-foreground">{pageItems.some(item => query.data?.items.includes(item)) ? "Required before creating or updating business records. You can continue browsing while setup is incomplete." : "Required before using the operation described below."}</p>
      <ul className="mt-2 space-y-2">{pageItems.map(item => <li key={item.id}><strong>{item.title} *</strong> · {item.ready ? "Complete" : "Missing — action required"}<p className="text-muted-foreground">{item.description}</p>{!item.ready && !item.canRepair && <p>Ask your company administrator to complete this item.</p>}</li>)}</ul>
      <p className="mt-2 text-muted-foreground">Fields marked * are mandatory.</p>
    </section>}
    {!query.data?.ready && <aside aria-label="Company setup" className="fixed bottom-4 left-1/2 z-[60] flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 items-center justify-between gap-3 rounded-lg border bg-background p-3 shadow-lg">
      <div className="min-w-0"><p className="text-sm">{query.isError ? "Company setup status is unavailable." : `Complete company setup · ${missing.length} ${missing.length === 1 ? "item" : "items"} remaining`}</p>{!query.isError && !!missing.length && <p className="mt-1 text-xs text-muted-foreground">Missing: {missing.map(item => item.title).join(", ")}</p>}</div>
      <Button size="sm" onClick={() => query.isError ? void query.refetch() : setOpen(true)}>{query.isError ? "Retry" : "Complete setup"}</Button>
    </aside>}
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal><Dialog.Overlay className="fixed inset-0 z-[70] bg-black/40"/><Dialog.Content className="fixed left-1/2 top-1/2 z-[71] max-h-[85dvh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-xl border bg-background p-5 shadow-xl">
        <Dialog.Title className="text-lg font-semibold">Complete company setup</Dialog.Title>
        <Dialog.Description className="mt-2 text-sm text-muted-foreground">* marks mandatory setup. Complete these essentials to create or update business records. You can still view records and repair settings.</Dialog.Description>
        <ul className="my-4 space-y-4">{missing.map(renderItem)}</ul>
        {!!moduleMissing.length && <details open={!missing.length} className="mb-4"><summary className="cursor-pointer text-sm font-medium">Module prerequisites</summary><p className="my-2 text-sm text-muted-foreground">Required only when you use the operation shown.</p><ul className="space-y-3">{moduleMissing.map(renderItem)}</ul></details>}
        {!missing.length && !moduleMissing.length && !query.isError && <p role="status" className="my-4">Company setup is complete.</p>}
        {query.isError && <p role="alert">Unable to refresh setup status. Try again.</p>}
        <div className="flex justify-end gap-2"><Button variant="outline" onClick={()=>void query.refetch()}>Check again</Button><Dialog.Close asChild><Button>Continue browsing</Button></Dialog.Close></div>
      </Dialog.Content></Dialog.Portal>
    </Dialog.Root>
  </>;
}
