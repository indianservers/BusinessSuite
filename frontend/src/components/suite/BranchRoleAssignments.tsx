import { NativeSelect } from "@/components/ui/native-select";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { useAuthStore } from "@/store/authStore";
import AdminVerification, { administratorStepUp } from "@/features/access/AdminVerification";

type Grant = { enabled: boolean; role: string; permissions: string[]; actions: string[]; scope: string; roleId?: number | null; roleVersion?: number };
type CustomRole = { id: number; name: string; module_key: string; permissions: string[]; actions: string[]; scope: string; version: number };
type Module = {key:string;label:string;installed:boolean;permissions:{name:string;description:string}[]};
type Policy = { version: number; all_branches: boolean; manage_access: boolean; use_home_branch: boolean; grants: { branch_id: number; can_write: boolean; module_grants?: Record<string, Grant> | null }[] };
const detail = (error:any) => typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "Request failed. Please retry.";

export default function BranchRoleAssignments({ userId, companyId, companyGrants }: { userId:number;companyId:number;companyGrants:Record<string,Grant> }) {
  const actor = useAuthStore(s=>s.user);
  const [draft,setDraft] = useState<Policy|null>(null);
  const [branchId,setBranchId] = useState("");
  const [reason,setReason] = useState("");
  const [message,setMessage] = useState("");
  const [busy,setBusy] = useState(false);
  const [verification,setVerification] = useState("");
  const headers = {"X-Suite-Organization":String(companyId),...(actor?.is_superuser?{"X-Suite-Branch":"all"}:{})};
  const policy = useQuery<Policy>({queryKey:["branch-roles",companyId,userId],queryFn:async()=>(await api.get(`/branches/access/${userId}`,{headers})).data,retry:false});
  const branches = useQuery<{branches:{id:number;name:string;is_active:boolean;state:string}[]}>({queryKey:["branch-role-choices",companyId],queryFn:async()=>(await api.get("/branches/manage",{headers})).data,retry:false});
  const catalog = useQuery<{modules:Module[];presets:Record<string,Record<string,Grant>>;roles:CustomRole[]}>({queryKey:["branch-role-catalog",companyId],queryFn:async()=>(await api.get("/access/catalog",{params:{companyId},headers})).data,retry:false});
  const value = draft || policy.data;
  if(policy.isError||branches.isError||catalog.isError)return <section className="rounded border p-4" role="alert"><h3 className="font-semibold">Branch-wise module permissions</h3><p>Unable to load branch roles: {detail(policy.error||branches.error||catalog.error)}</p><Button variant="outline" onClick={()=>{void policy.refetch();void branches.refetch();void catalog.refetch();}}>Retry branch permissions</Button></section>;
  if(!value||!branches.data||!catalog.data)return <p role="status">Loading branch-wise module permissions...</p>;
  const active = branches.data.branches.filter(b=>b.state==="active");
  const selectedId = Number(branchId || active.find(b=>value.grants.some(g=>g.branch_id===b.id))?.id || active[0]?.id);
  const selectedBranch = active.find(b=>b.id===selectedId);
  const selectedGrant = value.grants.find(g=>g.branch_id===selectedId);
  const enabled = catalog.data.modules.filter(m=>m.installed&&(companyGrants[m.key]?.enabled||selectedGrant?.module_grants?.[m.key]?.enabled)).sort((a,b)=>{const order=["hrms","crm","project_management","srm","fam"];return (order.includes(a.key)?order.indexOf(a.key):99)-(order.includes(b.key)?order.indexOf(b.key):99);});
  const change = (patch:object)=>setDraft({...value,grants:value.grants.map(g=>g.branch_id===selectedId?{...g,...patch}:g)});
  const setModule = (key:string,grant:Grant|null)=>{const modules={...selectedGrant?.module_grants};if(grant)modules[key]=grant;else delete modules[key];change({module_grants:modules});};
  const scopeText = "Applies only to the selected branch. A module admin here does not get access to another branch.";
  return <section className="my-4 grid gap-4 rounded-xl border border-primary/30 bg-primary/5 p-4" aria-label="Branch-wise module permissions">
    <h3 className="font-semibold">Branch-wise module permissions</h3><p className="text-sm">1. Save company module permissions below as the maximum access. 2. Choose a branch here. 3. Allow modules and roles for that branch, then save.</p><p className="text-sm font-medium">{scopeText}</p><a className="text-sm text-primary underline" href="#company-module-permissions">Set company maximum permissions below</a>
    <div className="grid gap-2 text-sm">
      <label className="flex items-center gap-2"><input type="checkbox" checked={value.use_home_branch} onChange={e=>setDraft({...value,use_home_branch:e.target.checked})}/> Also allow employee's home branch (explicit read-only settings still apply)</label>
      {actor?.is_superuser&&<><label className="flex items-center gap-2"><input type="checkbox" checked={value.all_branches} onChange={e=>setDraft({...value,all_branches:e.target.checked})}/> All current and future branches</label><label className="flex items-center gap-2"><input type="checkbox" checked={value.manage_access} onChange={e=>setDraft({...value,manage_access:e.target.checked})}/> May administer branch memberships</label></>}
      {value.all_branches&&<p role="note">All-branches access is enabled. Turn it off to restrict this person to individual branches.</p>}
    </div>
    <label className="grid gap-1 text-sm font-medium">Branch to configure<NativeSelect aria-label="Branch to configure" className="rounded border bg-background p-2" value={selectedBranch?.id??""} onChange={e=>setBranchId(e.target.value)}>{!active.length&&<option value="">No active branches</option>}{active.map(b=><option key={b.id} value={b.id}>{b.name}{value.grants.some(g=>g.branch_id===b.id)?" - assigned":" - no explicit access"}</option>)}</NativeSelect></label>
    {selectedBranch&&<div className="grid gap-3 rounded-lg border bg-background p-3">
      <label className="flex items-center gap-2 font-medium"><input aria-label={`Allow ${selectedBranch.name}`} type="checkbox" checked={!!selectedGrant} onChange={e=>setDraft({...value,grants:e.target.checked?[...value.grants,{branch_id:selectedId,can_write:false,module_grants:{}}]:value.grants.filter(g=>g.branch_id!==selectedId)})}/> Allow {selectedBranch.name}</label>
      {!selectedGrant&&<p className="text-sm">No explicit membership in this branch. All-branches or home-branch access, if enabled above, still applies.</p>}
      {selectedGrant&&<>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selectedGrant.can_write} onChange={e=>change({can_write:e.target.checked})}/> Allow writes permitted by module role</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selectedGrant.module_grants==null} onChange={e=>change({module_grants:e.target.checked?null:{}})}/> Use company module roles in this branch</label>
        {selectedGrant.module_grants==null?<p className="text-sm">Company roles apply in this branch. Uncheck to assign branch-specific modules and feature permissions.</p>:<>
          {!enabled.length&&<p className="text-sm">No company modules are enabled. Save company module permissions first, then reopen this user.</p>}
          {enabled.map(module=>{const grant=selectedGrant.module_grants?.[module.key];const ceiling=companyGrants[module.key]||{enabled:false,role:"none",permissions:[],actions:[],scope:"own"};const customRoles=catalog.data!.roles.filter(r=>r.module_key===module.key);const chosen=grant?.enabled?grant.roleId?`custom:${grant.roleId}`:catalog.data!.presets[module.key]?.[grant.role]?grant.role:"custom-features":"none";
            return <div key={module.key} className="grid gap-2 rounded border p-3">
              <label className="grid gap-1 text-sm font-medium">{module.label}<NativeSelect aria-label={`${selectedBranch.name} ${module.label} role`} className="rounded border bg-background p-2" value={chosen} onChange={e=>{
                if(e.target.value==="none"){setModule(module.key,null);return;}
                if(e.target.value==="custom-features"){setModule(module.key,{enabled:true,role:"custom",roleId:null,permissions:[],actions:ceiling.actions.includes("view")?["view"]:[],scope:ceiling.scope});return;}
                if(e.target.value.startsWith("custom:")){const role=customRoles.find(r=>r.id===Number(e.target.value.split(":")[1]));if(role)setModule(module.key,{enabled:true,role:role.name,roleId:role.id,roleVersion:role.version,permissions:role.permissions,actions:role.actions,scope:role.scope});return;}
                const preset=catalog.data!.presets[module.key][e.target.value];setModule(module.key,{...preset,permissions:preset.permissions.filter(p=>ceiling.permissions.includes(p)),actions:preset.actions.filter(a=>ceiling.actions.includes(a)),scope:ceiling.scope,roleId:null});
              }}><option value="none">No access</option>{["viewer","contributor","editor","manager","admin"].map(r=><option key={r} value={r} disabled={!ceiling.enabled}>{r==="admin"?"Admin (this branch only)":r}</option>)}<option value="custom-features" disabled={!ceiling.enabled}>Custom (select features)</option>{customRoles.map(r=><option key={r.id} value={`custom:${r.id}`} disabled={!ceiling.enabled}>{r.name}</option>)}</NativeSelect></label>
              {grant?.enabled&&<details><summary className="cursor-pointer text-sm">Feature permissions ({grant.permissions.length})</summary><p className="my-2 text-xs">Only features allowed by the saved company permissions can be granted. For precise restrictions, choose Custom (select features) and avoid broad admin/manage/view permissions, which include multiple features. Module actions also need to allow the operation.</p><div className="grid gap-2 sm:grid-cols-2">{module.permissions.filter(p=>ceiling?.permissions.includes(p.name)).map(permission=><label className="flex items-start gap-2 text-xs" key={permission.name}><input type="checkbox" checked={grant.permissions.includes(permission.name)} onChange={e=>setModule(module.key,{...grant,role:"custom",roleId:null,roleVersion:undefined,permissions:e.target.checked?[...grant.permissions,permission.name]:grant.permissions.filter(p=>p!==permission.name)})}/><span>{permission.description||permission.name}<small className="block text-muted-foreground">{permission.name}</small></span></label>)}</div><div className="mt-3 flex flex-wrap gap-3">{ceiling.actions.map(action=><label className="flex items-center gap-1 text-xs" key={action}><input type="checkbox" checked={grant.actions.includes(action)} onChange={e=>setModule(module.key,{...grant,role:"custom",roleId:null,roleVersion:undefined,actions:e.target.checked?[...grant.actions,action]:grant.actions.filter(a=>a!==action)})}/>{action}</label>)}</div></details>}
            </div>;
          })}
        </>}
      </>}
    </div>}
    {value.grants.filter(g=>!active.some(b=>b.id===g.branch_id)).length>0&&<p className="text-sm">Inactive branch memberships are retained. Restore those branches in Main Settings before editing their roles.</p>}
    <p className="text-xs text-muted-foreground">For an unlinked legacy account, saving creates a standard company membership after administrator verification. Revoked memberships must be restored explicitly first.</p>
    <label className="grid gap-1 text-sm">Reason for branch role change<input aria-label="Branch role change reason" className="rounded border bg-background p-2" value={reason} onChange={e=>setReason(e.target.value)}/></label>
    <AdminVerification value={verification} onChange={setVerification}/>
    <Button type="button" disabled={busy||!draft||reason.trim().length<5} onClick={async()=>{setBusy(true);setMessage("");try{const {version,...rest}=value;const proof=await administratorStepUp(verification);await api.put<Policy>(`/branches/access/${userId}`,{...rest,expected_version:version,reason},{headers:{...headers,"X-Access-Step-Up":proof.data.token}});setDraft(null);await policy.refetch();setVerification("");setReason("");setMessage("Branch modules, roles and feature permissions saved. Changes apply immediately.");}catch(error){setMessage(detail(error));}finally{setBusy(false);}}}>Save branch-wise permissions</Button>
    {message&&<p role="status">{message}</p>}
  </section>;
}
