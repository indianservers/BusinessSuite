import { useRecordScopeOwner } from "@/hooks/use-record-scope-owner";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

type Grant = { branch_id: number; can_write: boolean; module_grants?: Record<string, unknown> | null };
type Policy = { version: number; all_branches: boolean; manage_access: boolean; use_home_branch: boolean; grants: Grant[] };

export default function BranchMembershipSettings({ branches, scope }: { scope: string; branches: {id:number;name:string;can_write:boolean;is_active:boolean}[] }) {
  const owns = useRecordScopeOwner();
  const actor = useAuthStore(s => s.user);
  const members = useQuery({queryKey:["settings-branch-members",actor?.id,scope],queryFn:({signal})=>api.get<{id:number;email:string;is_superuser:boolean}[]>("/branches/access/users",{signal}).then(r=>r.data)});
  const [target,setTarget] = useState("");
  const [policy,setPolicy] = useState<Policy|null>(null);
  const [reason,setReason] = useState("");
  const [message,setMessage] = useState("");
  const [busy,setBusy] = useState(false);
  return <details className="settings-panel"><summary>Assign branch memberships</summary><p>Delegate access within your authorized branches. Module roles continue to limit what each user can do.</p>
    {members.isError && <p role="alert">Unable to load authorized members.</p>}
    <label>Company member<NativeSelect loading={members.isFetching} error={members.isError} aria-label="Branch access member" value={target} disabled={busy || members.isPending} onChange={async e=>{if(!owns())return;const id=e.target.value;setTarget(id);setPolicy(null);setMessage("");if(!id)return;setBusy(true);try{const response=await api.get<Policy>(`/branches/access/${id}`);if(owns())setPolicy(response.data);}catch{if(owns())setMessage("Unable to load this member's branch access.");}finally{if(owns())setBusy(false);}}}><option value="">Choose a member</option>{members.data?.filter(m=>!m.is_superuser && m.id!==actor?.id).map(m=><option key={m.id} value={m.id}>{m.email}</option>)}</NativeSelect></label>
    {policy && <CompactForm onSubmit={async e=>{e.preventDefault();if(!owns()||busy)return;setBusy(true);setMessage("");try{const {version,...value}=policy;const response=await api.put<Policy>(`/branches/access/${target}`,{...value,expected_version:version,reason:reason.trim()});if(!owns())return;setPolicy(response.data);setReason("");setMessage("Branch memberships saved.");}catch(err:any){if(owns())setMessage(typeof err?.response?.data?.detail==="string"?err.response.data.detail:"Unable to save branch access.");}finally{if(owns())setBusy(false);}}}>
      <label className="settings-check"><input type="checkbox" checked={policy.use_home_branch} onChange={e=>setPolicy({...policy,use_home_branch:e.target.checked})}/>Allow employee's home branch</label>
      {branches.filter(b=>b.is_active).map(b=>{const grant=policy.grants.find(g=>g.branch_id===b.id);return <div className="settings-membership-row" key={b.id}><label className="settings-check"><input type="checkbox" checked={!!grant} onChange={e=>setPolicy({...policy,grants:e.target.checked?[...policy.grants,{branch_id:b.id,can_write:false}]:policy.grants.filter(g=>g.branch_id!==b.id)})}/>{b.name}</label><label className="settings-check"><input type="checkbox" checked={!!grant?.can_write} disabled={!grant || !b.can_write} onChange={e=>setPolicy({...policy,grants:policy.grants.map(g=>g.branch_id===b.id?{...g,can_write:e.target.checked}:g)})}/>Allow permitted writes</label></div>;})}
      <label>Reason for membership change<input required minLength={5} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/></label><Button type="submit" variant="outline" className="settings-primary" disabled={busy || reason.trim().length<5}>Save branch memberships</Button>
    </CompactForm>}
    {message && <p role="status">{message}</p>}
  </details>;
}
