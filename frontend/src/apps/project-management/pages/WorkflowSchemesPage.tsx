import { useEffect, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { workspaceError } from "./workspaceTypes";

const base = "/project-management";
const statuses = ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"];
const fields = ["assignee", "due_date", "description"] as const;
type RequiredField = typeof fields[number];
type Transition = {source:string; target:string; required_fields:RequiredField[]; approval_user_ids?:number[]};
type Scheme = {revision:number; enabled:boolean; transitions:Transition[]; work_type_transitions?:Record<string,Transition[]>};
type Project = {id:number; name:string; can_edit:boolean; workspace_id:number|null; is_archived:boolean};

export default function WorkflowSchemesPage() {
 const [people,setPeople] = useState<{id:number;name:string;email?:string}[]>([]);
 const [projects,setProjects] = useState<Project[]>([]);
 const [workType,setWorkType] = useState("");
 const [types,setTypes] = useState<string[]>([]);
 const [project,setProject] = useState("");
 const [scheme,setScheme] = useState<Scheme>();
 const [dirty,setDirty] = useState(false);
 const [busy,setBusy] = useState(false);
 const [error,setError] = useState("");
 const [notice,setNotice] = useState("");
 const [reload,setReload] = useState(0);
 useEffect(()=>{let active=true; void api.get<{projects:Project[];people:{id:number;name:string;email?:string}[]}>(`${base}/management/home`).then(r=>{
  if(active){setProjects(r.data.projects.filter(p=>p.can_edit&&p.workspace_id&&!p.is_archived));setPeople(r.data.people);}
 }).catch(e=>{if(active)setError(workspaceError(e));}); return()=>{active=false;};},[]);
 useEffect(()=>{void api.get<{types:{name:string;archived:boolean}[]}>(`${base}/task-types`).then(r=>setTypes(r.data.types.filter(t=>!t.archived).map(t=>t.name))).catch(e=>setError(workspaceError(e)));},[]);
 useEffect(()=>{let active=true;setWorkType("");setScheme(undefined);setDirty(false);setError("");setNotice("");
  if(project) void api.get<Scheme>(`${base}/projects/${project}/workflow-scheme`).then(r=>{if(active)setScheme(r.data);}).catch(e=>{if(active)setError(workspaceError(e));});
  return()=>{active=false;};
 },[project,reload]);
 useEffect(()=>{const guard=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue="";}};window.addEventListener("beforeunload",guard);return()=>window.removeEventListener("beforeunload",guard);},[dirty]);
 function change(next:Scheme){setScheme(next);setDirty(true);setNotice("");}
 const transitions = scheme ? (workType ? scheme.work_type_transitions?.[workType] ?? scheme.transitions : scheme.transitions) : [];
 function changeRules(rules:Transition[]){if(scheme)change(workType?{...scheme,work_type_transitions:{...scheme.work_type_transitions,[workType]:rules}}:{...scheme,transitions:rules});}
 function edit(index:number, values:Partial<Transition>){changeRules(transitions.map((r,i)=>i===index?{...r,...values}:r));}
 async function save(){if(!scheme)return;setBusy(true);setError("");try{const response=await api.put<Scheme>(`${base}/projects/${project}/workflow-scheme`,scheme);setScheme(response.data);setDirty(false);setNotice("Workflow saved");}catch(e){setError(workspaceError(e));}finally{setBusy(false);}}
 return <main className="mx-auto max-w-5xl space-y-5 p-4">
  <header><h1 className="page-title">Project workflows</h1><p className="page-description">Choose allowed status changes and the information each transition requires.</p></header>
  <a className="inline-block underline" href="/pms/transition-approvals">Review transition approvals</a>
  <p className="text-sm text-muted-foreground">When enabled, only listed transitions are allowed. Existing completion, checklist and blocker checks still apply. Disabling the policy restores standard status changes.</p>
  {error&&<p role="alert" className="text-destructive">{error}</p>}{notice&&<p role="status">{notice}</p>}
  <label className="block space-y-2">Project<NativeSelect aria-label="Project" value={project} disabled={busy||dirty} onChange={e=>setProject(e.target.value)}><option value="">Choose a project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</NativeSelect></label>
  {!projects.length&&<p>You need project editing access to a project in a workspace to configure workflows.</p>}
  {scheme&&<fieldset disabled={busy} className="space-y-4">
   <label className="flex items-center gap-2"><input type="checkbox" checked={scheme.enabled} onChange={e=>change({...scheme,enabled:e.target.checked})}/>Enforce allowed transitions</label>
   <label className="block">Work type<NativeSelect aria-label="Work type" value={workType} onChange={e=>setWorkType(e.target.value)}><option value="">Project default</option>{[...new Set([...types,...Object.keys(scheme.work_type_transitions||{})])].map(t=><option key={t}>{t}</option>)}</NativeSelect></label>
   {workType&&<p className="text-sm">{scheme.work_type_transitions?.[workType]?"This type has its own transitions.":"This type inherits the project default. Editing creates an override."}</p>}
   {workType&&scheme.work_type_transitions?.[workType]&&<Button variant="outline" onClick={()=>{const scopes={...scheme.work_type_transitions};delete scopes[workType];change({...scheme,work_type_transitions:scopes});}}>Use project default for this type</Button>}
   <div className="space-y-3">{transitions.map((r,i)=><div key={i} className="flex flex-wrap items-end gap-3 rounded border p-3">
    <label>From<NativeSelect aria-label={`From status ${i+1}`} value={r.source} onChange={e=>edit(i,{source:e.target.value})}>{statuses.map(s=><option key={s}>{s}</option>)}</NativeSelect></label>
    <label>To<NativeSelect aria-label={`To status ${i+1}`} value={r.target} onChange={e=>edit(i,{target:e.target.value})}>{statuses.map(s=><option key={s}>{s}</option>)}</NativeSelect></label>
    <fieldset className="flex flex-wrap gap-3"><legend className="text-sm">Required information</legend>{fields.map(f=><label key={f} className="flex items-center gap-1"><input type="checkbox" checked={r.required_fields.includes(f)} onChange={e=>edit(i,{required_fields:e.target.checked?[...r.required_fields,f]:r.required_fields.filter(x=>x!==f)})}/>{f==="due_date"?"Due date":f==="assignee"?"Assignee":"Description"}</label>)}</fieldset>
    <Button variant="outline" aria-label={`Remove transition ${i+1}`} onClick={()=>changeRules(transitions.filter((_,n)=>n!==i))}>Remove</Button>
    <fieldset className="w-full space-y-2"><legend className="text-sm font-medium">Approval route (in order)</legend>
     {(r.approval_user_ids||[]).map((uid,j)=><div key={j} className="flex flex-wrap items-center gap-2"><label>Step {j+1}<NativeSelect aria-label={`Approver for transition ${i+1} step ${j+1}`} value={uid||""} onChange={e=>edit(i,{approval_user_ids:(r.approval_user_ids||[]).map((id,n)=>n===j?Number(e.target.value):id)})}><option value="">Choose a reviewer</option>{people.map(p=><option key={p.id} value={p.id}>{p.name||p.email||`Person ${p.id}`}</option>)}</NativeSelect></label><Button variant="outline" aria-label={`Remove approval step ${j+1} from transition ${i+1}`} onClick={()=>edit(i,{approval_user_ids:(r.approval_user_ids||[]).filter((_,n)=>n!==j)})}>Remove approval step</Button></div>)}
     <Button variant="outline" disabled={(r.approval_user_ids||[]).length>=10} onClick={()=>edit(i,{approval_user_ids:[...r.approval_user_ids||[],0]})}>Add approval step</Button>
     <p className="text-xs text-muted-foreground">No steps means no approval is required. Reviewers must have active project access and cannot approve their own requests.</p>
    </fieldset>
   </div>)}</div>
   <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={transitions.length>=30} onClick={()=>changeRules([...transitions,{source:"To Do",target:"In Progress",required_fields:[]}])}>Add transition</Button><Button disabled={!dirty} onClick={()=>void save()}>Save workflow</Button><Button variant="outline" disabled={!dirty} onClick={()=>setReload(n=>n+1)}>Discard changes and reload</Button></div>
   {dirty&&<p role="status" className="text-sm">Unsaved changes. Save or discard before choosing another project.</p>}
  </fieldset>}
 </main>;
}
