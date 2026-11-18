import {useAiAdministration,AiAdministrativeNotice} from "@/hooks/use-ai-administration";
import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRecordScope } from "@/shared/records/Record360Workspace";
import { useRecordScopeOwner } from "@/hooks/use-record-scope-owner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { toast } from "@/hooks/use-toast";
import { aiAgentsApi, type AiAgent, type AiPermissionRule } from "@/services/aiAgentsApi";

export default function AiAgentPermissionsPage() {
  const scope=useRecordScope();
  return <ScopedPermissionsPage key={scope} scope={scope}/>;
}
function ScopedPermissionsPage({scope}:{scope:string}) {
  const ownsScope=useRecordScopeOwner();
  const canAdmin=useAiAdministration("manage_users");
  const [saving,setSaving]=useState(false);
  const [agents, setAgents] = useState<AiAgent[]>([]);
  const [rules, setRules] = useState<AiPermissionRule[]>([]);

  useEffect(() => {
    if(!canAdmin)return;
    Promise.all([aiAgentsApi.getAgents(), aiAgentsApi.getPermissions()])
      .then(([agentsResponse, rulesResponse]) => {
        if(!ownsScope())return;
        setAgents(agentsResponse.data);
        setRules(rulesResponse.data);
      })
      .catch(() => {if(ownsScope())toast({ title: "Permission matrix unavailable", description:"Could not load the permission rules.", variant: "destructive" });});
  }, [canAdmin]);

  const update = (index: number, patch: Partial<AiPermissionRule>) => setRules((items) => items.map((item, current) => current === index ? { ...item, ...patch } : item));
  const add = () => setRules((items) => [...items, { agent_id: agents[0]?.id || 0, can_use: true, can_configure: false, can_approve_actions: false, can_view_logs: false, can_export_conversations: false }]);
  const save = async () => {
    if(saving||!ownsScope())return;
    if(rules.some(rule=>!rule.role_id&&!rule.user_id)){toast({title:"Choose a role or user for every rule",variant:"destructive"});return;}
    setSaving(true);
    try{await aiAgentsApi.updatePermissions(rules.filter(rule=>rule.agent_id));if(!ownsScope())return;const response=await aiAgentsApi.getPermissions();if(!ownsScope())return;setRules(response.data);toast({title:"AI permission matrix saved"});}
    catch(error){if(!ownsScope())return;const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;toast({title:"Could not save permission rules",description:typeof detail==="string"?detail:"Your rules are kept for retry.",variant:"destructive"});}
    finally{if(ownsScope())setSaving(false);}
  };

  if(!canAdmin)return <AiAdministrativeNotice permission="AI configuration and user-management"/>;
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">AI Permission Matrix</h1>
          <p className="text-sm text-muted-foreground">Control who can use, configure, approve, view logs, and export conversations.</p>
        </div>
        <div className="flex gap-2"><Button variant="outline" onClick={add} disabled={saving||!agents.length}>Add rule</Button><Button onClick={save} disabled={saving||!rules.length}>Save</Button></div>
      </div>
      <Card>
        <CardHeader><CardTitle>Rules</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {rules.map((rule, index) => (
            <fieldset disabled={saving} key={rule.id ? `saved:${rule.id}` : `draft:${index}`} className="grid min-w-0 gap-3 rounded-md border p-3 md:grid-cols-2">
              <NativeSelect aria-label={`Agent for rule ${index+1}`} className="rounded-md border bg-background px-3 py-2 text-sm" value={rule.agent_id} onChange={(event) => update(index, { agent_id: Number(event.target.value) })}>
                {agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
              </NativeSelect>
              <PermissionTargets rule={rule} index={index} scope={scope} update={patch=>update(index,patch)}/>
              <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
                {(["can_use", "can_configure", "can_approve_actions", "can_view_logs", "can_export_conversations"] as const).map((field) => (
                  <label key={field} className="flex items-center gap-1 rounded border p-2"><input type="checkbox" checked={Boolean(rule[field])} onChange={(event) => update(index, { [field]: event.target.checked })} /> {field.replace("can_", "").replace(/_/g, " ")}</label>
                ))}
              </div>
            </fieldset>
          ))}
          {!rules.length ? <p className="text-sm text-muted-foreground">No permission rules yet. Defaults apply until a rule is saved.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}

function PermissionTargets({rule,index,scope,update}:{rule:AiPermissionRule;index:number;scope:string;update:(patch:Partial<AiPermissionRule>)=>void}){
  const [search,setSearch]=useState(''),[page,setPage]=useState(1);
  const query=useQuery({queryKey:['ai-permission-targets',scope,search,page,rule.user_id],queryFn:()=>aiAgentsApi.getPermissionTargets({search,page,selected_user:rule.user_id||undefined}).then(r=>r.data),retry:false});
  const users=[...(query.data?.users||[])];
  const selected=query.data?.selected_user;
  if(selected&&!users.some(user=>user.id===selected.id))users.unshift(selected);
  return <div className="min-w-0 space-y-2">
    <label className="block">Role<NativeSelect aria-label={`Role for rule ${index+1}`} disabled={query.isPending||query.isError} value={rule.role_id||''} onChange={e=>update({role_id:e.target.value?Number(e.target.value):null})}>
      <option value="">Any role</option>{rule.role_id&&!query.data?.roles.some(role=>role.id===rule.role_id)&&<option value={rule.role_id}>Selected role unavailable</option>}{query.data?.roles.map(role=><option key={role.id} value={role.id}>{role.name}</option>)}
    </NativeSelect></label>
    <label className="block">Find a user<Input aria-label={`Find user for rule ${index+1}`} value={search} maxLength={100} onChange={e=>{setSearch(e.target.value);setPage(1);}} placeholder="Name or email"/></label>
    <label className="block">User<NativeSelect aria-label={`User for rule ${index+1}`} disabled={query.isPending||query.isError} value={rule.user_id||''} onChange={e=>update({user_id:e.target.value?Number(e.target.value):null})}>
      <option value="">Any user</option>{rule.user_id&&!users.some(user=>user.id===rule.user_id)&&<option value={rule.user_id}>Selected user unavailable</option>}{users.map(user=><option key={user.id} value={user.id}>{user.name} · {user.email}</option>)}
    </NativeSelect></label>
    <p className="text-xs text-muted-foreground">Choose a role or user. A user-specific rule takes precedence.</p>
    {query.isError&&<p role="alert">Could not load role and user choices. <Button type="button" variant="outline" onClick={()=>void query.refetch()}>Retry choices</Button></p>}
    <div className="flex gap-2"><Button type="button" variant="outline" disabled={page===1||query.isFetching} onClick={()=>setPage(p=>p-1)}>Previous users</Button><Button type="button" variant="outline" disabled={!query.data?.has_more||query.isFetching} onClick={()=>setPage(p=>p+1)}>More users</Button></div>
  </div>;
}
