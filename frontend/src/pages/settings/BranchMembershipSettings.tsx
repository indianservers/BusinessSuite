import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

type Grant = { branch_id: number; can_write: boolean; module_grants?: Record<string, unknown> | null };
type Policy = { version: number; all_branches: boolean; manage_access: boolean; use_home_branch: boolean; grants: Grant[] };

export default function BranchMembershipSettings({ branches }: { branches: {id:number;name:string;can_write:boolean;is_active:boolean}[] }) {
  const actor = useAuthStore(s => s.user);
  const members = useQuery({queryKey:["settings-branch-members",actor?.id],queryFn:()=>api.get<{id:number;email:string;is_superuser:boolean}[]>("/branches/access/users").then(r=>r.data)});
  const [target,setTarget] = useState("");
  const [policy,setPolicy] = useState<Policy|null>(null);
  const [reason,setReason] = useState("");
  const [message,setMessage] = useState("");
  const [busy,setBusy] = useState(false);
  return <details className="settings-panel"><summary>Assign branch memberships</summary><p>Delegate access within your authorized branches. Module roles continue to limit what each user can do.</p>
    {members.isError && <p role="alert">Unable to load authorized members.</p>}
    <label>Company member<select aria-label="Branch access member" value={target} disabled={busy || members.isPending} onChange={async e=>{const id=e.target.value;setTarget(id);setPolicy(null);setMessage("");if(!id)return;setBusy(true);try{setPolicy((await api.get<Policy>(`/branches/access/${id}`)).data);}catch{setMessage("Unable to load this member's branch access.");}finally{setBusy(false);}}}><option value="">Choose a member</option>{members.data?.filter(m=>!m.is_superuser && m.id!==actor?.id).map(m=><option key={m.id} value={m.id}>{m.email}</option>)}</select></label>
    {policy && <form onSubmit={async e=>{e.preventDefault();setBusy(true);setMessage("");try{const {version,...value}=policy;setPolicy((await api.put<Policy>(`/branches/access/${target}`,{...value,expected_version:version,reason:reason.trim()})).data);setReason("");setMessage("Branch memberships saved.");}catch(err:any){setMessage(typeof err?.response?.data?.detail==="string"?err.response.data.detail:"Unable to save branch access.");}finally{setBusy(false);}}}>
      <label className="settings-check"><input type="checkbox" checked={policy.use_home_branch} onChange={e=>setPolicy({...policy,use_home_branch:e.target.checked})}/>Allow employee's home branch</label>
      {branches.filter(b=>b.is_active).map(b=>{const grant=policy.grants.find(g=>g.branch_id===b.id);return <div className="settings-membership-row" key={b.id}><label className="settings-check"><input type="checkbox" checked={!!grant} onChange={e=>setPolicy({...policy,grants:e.target.checked?[...policy.grants,{branch_id:b.id,can_write:false}]:policy.grants.filter(g=>g.branch_id!==b.id)})}/>{b.name}</label><label className="settings-check"><input type="checkbox" checked={!!grant?.can_write} disabled={!grant || !b.can_write} onChange={e=>setPolicy({...policy,grants:policy.grants.map(g=>g.branch_id===b.id?{...g,can_write:e.target.checked}:g)})}/>Allow permitted writes</label></div>;})}
      <label>Reason for membership change<input required minLength={5} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label><button className="settings-primary" disabled={busy || reason.trim().length<5}>Save branch memberships</button>
    </form>}
    {message && <p role="status">{message}</p>}
  </details>;
}
