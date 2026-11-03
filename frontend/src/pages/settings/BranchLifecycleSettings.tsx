import CompactForm from "@/components/forms/CompactForm";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

type Branch = { id: number; name: string; code: string; is_active: boolean; can_manage: boolean; can_trash: boolean; state: "active" | "archived" | "trash" | "protected"; version: number; deleted_at: string | null; retain_until: string | null };
type Action = "rename" | "trash" | "protect" | "restore";
const titles: Record<Action, string> = {rename:"Rename branch",trash:"Move branch to Trash",protect:"Delete from trash",restore:"Restore branch"};
const reasons: Record<Action, string> = {rename:"Rename branch in Main Settings",trash:"Branch no longer in use",protect:"Move branch to protected recovery",restore:"Restore branch from recovery"};
const date = (value: string) => new Date(value).toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"});

export default function BranchLifecycleSettings() {
  const qc = useQueryClient();
  const branches = useQuery({queryKey:["settings-branch-lifecycle"],queryFn:()=>api.get<{branches:Branch[];retention_days:number}>("/branches/manage").then(r=>r.data),staleTime:0});
  const [tab,setTab] = useState<"active"|"trash"|"protected">("active");
  const [pending,setPending] = useState<{branch:Branch;action:Action}|null>(null);
  const [name,setName] = useState("");
  const [reason,setReason] = useState("");
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [message,setMessage] = useState("");
  if(branches.isPending) return <section className="settings-panel" role="status">Loading branches and recovery…</section>;
  if(branches.isError) return <section className="settings-panel" role="alert">Unable to load branch recovery. <button onClick={()=>void branches.refetch()}>Retry</button></section>;
  const all = branches.data.branches;
  const counts = {active:all.filter(b=>b.state==="active").length,trash:all.filter(b=>["trash","archived"].includes(b.state)).length,protected:all.filter(b=>b.state==="protected").length};
  const visible = all.filter(b=>tab==="trash"?["trash","archived"].includes(b.state):b.state===tab);
  function open(branch:Branch,action:Action){setPending({branch,action});setName(branch.name);setReason(reasons[action]);setError("");setMessage("");}
  return <section className="settings-panel">
    <h2>Manage branches & recovery</h2><p>Rename branches here. Deleting a branch stops branch access without deleting its records or memberships. Restore reactivates the same branch and its saved permissions.</p>
    <div className="settings-branch-tabs" role="tablist" aria-label="Branch status">
      {(["active","trash","protected"] as const).map(key=><button key={key} type="button" role="tab" aria-selected={tab===key} onClick={()=>{setTab(key);setError("");setMessage("");}}>{key==="active"?"Active branches":key==="trash"?"Trash":"Protected recovery"} ({counts[key]})</button>)}
    </div>
    {tab!=="active" && <p>Recovery is retained for at least {branches.data.retention_days} days, including after Delete from trash. There is no permanent-delete action or automatic purge after day 45.</p>}
    {message && <p role="status">{message}</p>}
    {error && !pending && <p role="alert">{error}</p>}
    <ul className="settings-branch-list">{visible.map(branch=><li key={branch.id}>
      <div><strong>{branch.name}</strong><small>{branch.code} · {branch.state==="protected"?"Protected recovery":branch.state==="trash"?"In Trash":branch.state==="archived"?"Previously archived":"Active"}</small>{branch.retain_until && <small>Protected until at least {date(branch.retain_until)}. Restore remains available.</small>}</div>
      <div className="settings-branch-actions">{branch.can_manage ? branch.state==="active" ? <><button type="button" onClick={()=>open(branch,"rename")}>Rename</button><button type="button" disabled={!branch.can_trash} title={!branch.can_trash?"Keep at least one active branch":undefined} onClick={()=>open(branch,"trash")}>Move to Trash</button></> : <><button type="button" onClick={()=>open(branch,"restore")}>Restore</button>{branch.state==="trash" && <button type="button" onClick={()=>open(branch,"protect")}>Delete from trash</button>}</> : <span>View only</span>}</div>
    </li>)}</ul>
    {!visible.length && <p role="status">{tab==="active"?"No active branches available.":tab==="trash"?"Trash is empty.":"No branches in protected recovery."}</p>}
    <Dialog open={!!pending} onOpenChange={value=>{if(!value&&!busy){setPending(null);setError("");}}}><DialogContent className="settings-branch-dialog">
      <DialogTitle className="text-lg font-semibold">{pending?titles[pending.action]:"Branch action"}</DialogTitle>
      {pending && <CompactForm onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");const {branch,action}=pending;
        try{
          const body={reason:reason.trim(),expected_version:branch.version};
          if(action==="rename")await api.patch(`/branches/${branch.id}`,{...body,name:name.trim()});else await api.post(`/branches/${branch.id}/${action}`,body);
          setPending(null);setMessage(action==="rename"?"Branch renamed. Its records and permissions are unchanged.":action==="restore"?"Branch restored with its existing records and memberships.":action==="protect"?"Moved to protected recovery. You can still restore this branch.":"Branch moved to Trash. Its records and permissions are retained.");
          setTab(action==="trash"?"trash":action==="protect"?"protected":"active");
          if(action==="trash" && sessionStorage.getItem("suite-branch")===String(branch.id)){sessionStorage.removeItem("suite-branch");window.location.reload();return;}
          await qc.invalidateQueries({predicate:q=>q.queryKey.some(k=>typeof k==="string" && (/branch/.test(k)||k==="shared-settings"))});
        }catch(err:any){setError(typeof err?.response?.data?.detail==="string"?err.response.data.detail:"Could not complete branch action. Refresh and try again.");}finally{setBusy(false);}
      }}>
        <p><strong>{pending.branch.name}</strong> · {pending.branch.code}</p>
        {pending.action==="rename" && <label>New branch name<input autoFocus required maxLength={150} value={name} disabled={busy} onChange={e=>setName(e.target.value)}/></label>}
        {pending.action==="trash" && <p>Users will lose access to this branch until it is restored. Customers, employees, sales and all other records stay in place.</p>}
        {pending.action==="protect" && <p>This removes the branch from ordinary Trash and starts another full 45 days of protected recovery. It does not permanently delete anything. Find it under Protected recovery to restore it.</p>}
        {pending.action==="restore" && <p>This reactivates the branch and restores access through its existing memberships. Current company permissions and user status still apply.</p>}
        <label>Reason<input required minLength={5} maxLength={1000} value={reason} disabled={busy} onChange={e=>setReason(e.target.value)}/></label>
        {error && <p role="alert">{error}</p>}
        <div className="settings-branch-actions"><button type="button" disabled={busy} onClick={()=>setPending(null)}>Cancel</button><button className="settings-primary" disabled={busy||reason.trim().length<5||(pending.action==="rename"&&!name.trim())}>{busy?"Saving…":titles[pending.action]}</button></div>
      </CompactForm>}
    </DialogContent></Dialog>
  </section>;
}
