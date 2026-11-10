import { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import { workspaceError } from "./workspaceTypes";
import { syncScope } from "@/shared/record-sync/store";
import { useMobileContext } from "@/components/mobile/useMobileContext";
import { useMobile } from "@/components/mobile/useMobile";
import { MobileDisclosure } from "@/components/mobile/MobilePrimitives";
import "./workflow-schemes-mobile.css";

const base = "/project-management";
const statuses = ["Backlog", "To Do", "In Progress", "In Review", "Blocked", "Done"];
const fields = ["assignee", "due_date", "description"] as const;
type RequiredField = typeof fields[number];
type Transition = {source:string; target:string; required_fields:RequiredField[]; approval_user_ids?:number[]};
type Scheme = {revision:number; enabled:boolean; transitions:Transition[]; work_type_transitions?:Record<string,Transition[]>};
type Project = {id:number; name:string; can_edit:boolean; workspace_id:number|null; is_archived:boolean};

export default function WorkflowSchemesPage() {
 const scope=useMobileContext();
 return <WorkflowContents key={scope}/>;
}
function WorkflowContents() {
 const phone=useMobile(480);
 const saving=useRef(false),mounted=useRef(true),ownerScope=useRef(syncScope());
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const [homeReload,setHomeReload]=useState(0),[typesReload,setTypesReload]=useState(0);
 const [homeLoading,setHomeLoading]=useState(true),[typesLoading,setTypesLoading]=useState(true),[schemeLoading,setSchemeLoading]=useState(false);
 const [homeError,setHomeError]=useState(""),[typesError,setTypesError]=useState(""),[schemeError,setSchemeError]=useState("");
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
 useEffect(()=>{let active=true;const owned=phone,scope=syncScope();const current=()=>active&&(!owned||scope===syncScope());setHomeLoading(true); void api.get<{projects:Project[];people:{id:number;name:string;email?:string}[]}>(`${base}/management/home`).then(r=>{
  if(current()){setHomeError("");setProjects(r.data.projects.filter(p=>p.can_edit&&p.workspace_id&&!p.is_archived));setPeople(r.data.people);}
 }).catch(e=>{if(current()){setHomeError(workspaceError(e));if(!phone)setError(workspaceError(e));}}).finally(()=>{if(current())setHomeLoading(false);}); return()=>{active=false;};},[homeReload]);
 useEffect(()=>{let active=true;const owned=phone,scope=syncScope();const current=()=>active&&(!owned||scope===syncScope());setTypesLoading(true);void api.get<{types:{name:string;archived:boolean}[]}>(`${base}/task-types`).then(r=>{if(current()){setTypesError("");setTypes(r.data.types.filter(t=>!t.archived).map(t=>t.name));}}).catch(e=>{if(current()){setTypesError(workspaceError(e));if(!phone)setError(workspaceError(e));}}).finally(()=>{if(current())setTypesLoading(false);});return()=>{active=false;};},[typesReload]);
 useEffect(()=>{let active=true;const owned=phone,scope=syncScope();const current=()=>active&&(!owned||scope===syncScope());setWorkType("");setScheme(undefined);setDirty(false);setError("");setNotice("");setSchemeError("");setSchemeLoading(!!project);
  if(project) void api.get<Scheme>(`${base}/projects/${project}/workflow-scheme`).then(r=>{if(current())setScheme(r.data);}).catch(e=>{if(current()){setSchemeError(workspaceError(e));if(!phone)setError(workspaceError(e));}}).finally(()=>{if(current())setSchemeLoading(false);});
  return()=>{active=false;};
 },[project,reload]);
 useEffect(()=>{const guard=(e:BeforeUnloadEvent)=>{if(dirty){e.preventDefault();e.returnValue="";}};window.addEventListener("beforeunload",guard);return()=>window.removeEventListener("beforeunload",guard);},[dirty]);
 useEffect(()=>{
  if(!phone)return;
  const click=(event:MouseEvent)=>{
   if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
   const link=(event.target as Element)?.closest?.("a[href]") as HTMLAnchorElement|null;
   if(!link||link.hasAttribute("download")||link.target&&link.target!=="_self")return;
   const next=new URL(link.href,location.href);
   if(next.origin===location.origin&&next.pathname===location.pathname&&next.search===location.search)return;
   if(saving.current||dirty&&!window.confirm("Discard unsaved workflow changes?")){event.preventDefault();event.stopPropagation();}
   else if(dirty)setDirty(false);
  };
  document.addEventListener("click",click,true);return()=>document.removeEventListener("click",click,true);
 },[phone,dirty]);
 function change(next:Scheme){setScheme(next);setDirty(true);setNotice("");}
 const transitions = scheme ? (workType ? scheme.work_type_transitions?.[workType] ?? scheme.transitions : scheme.transitions) : [];
 function changeRules(rules:Transition[]){if(scheme)change(workType?{...scheme,work_type_transitions:{...scheme.work_type_transitions,[workType]:rules}}:{...scheme,transitions:rules});}
 function edit(index:number, values:Partial<Transition>){changeRules(transitions.map((r,i)=>i===index?{...r,...values}:r));}
 async function save(){
  if(!scheme||phone&&(saving.current||busy||!dirty||ownerScope.current!==syncScope()||!projects.some(p=>String(p.id)===project)))return;
  const owned=phone,scope=syncScope();const current=()=>!owned||mounted.current&&scope===syncScope();
  if(owned)saving.current=true;setBusy(true);setError("");
  try{const response=await api.put<Scheme>(`${base}/projects/${project}/workflow-scheme`,scheme);if(!current())return;setScheme(response.data);setDirty(false);setNotice("Workflow saved");}
  catch(e){if(current())setError(workspaceError(e));}
  finally{if(current()){saving.current=false;setBusy(false);}}
 }
 function discard(){if(phone&&(saving.current||busy||dirty&&!window.confirm("Discard unsaved workflow changes and reload?")))return;setReload(n=>n+1);}
 return <main className="workflow-schemes mx-auto max-w-5xl space-y-5 p-4" aria-busy={phone?busy:undefined}>
  <header><h1 className="page-title">Project workflows</h1><p className="page-description">Choose allowed status changes and the information each transition requires.</p></header>
  <a className="inline-block underline" href="/pms/transition-approvals">Review transition approvals</a>
  <p className="text-sm text-muted-foreground">When enabled, only listed transitions are allowed. Existing completion, checklist and blocker checks still apply. Disabling the policy restores standard status changes.</p>
  {error&&<p role="alert" className="text-destructive">{error}</p>}{notice&&<p role="status">{notice}</p>}
  {phone&&busy&&<p role="status">Saving workflow…</p>}
  {phone&&homeLoading&&<p role="status">Loading projects and reviewers…</p>}
  {phone&&homeError&&<div><p role="alert">{homeError}</p><Button variant="outline" disabled={homeLoading||busy} onClick={()=>setHomeReload(n=>n+1)}>Retry projects and reviewers</Button></div>}
  {phone&&typesLoading&&<p role="status">Loading work types…</p>}
  {phone&&typesError&&<div><p role="alert">{typesError}</p><Button variant="outline" disabled={typesLoading||busy} onClick={()=>setTypesReload(n=>n+1)}>Retry work types</Button></div>}
  {phone&&schemeLoading&&<p role="status">Loading project workflow…</p>}
  {phone&&schemeError&&<div><p role="alert">{schemeError}</p><Button variant="outline" disabled={schemeLoading||busy} onClick={()=>setReload(n=>n+1)}>Retry project workflow</Button></div>}
  <label className="block space-y-2">Project<NativeSelect aria-label="Project" loading={phone&&homeLoading} error={phone&&!!homeError} value={project} disabled={busy||dirty||phone&&homeLoading} onChange={e=>setProject(e.target.value)}><option value="">Choose a project</option>{projects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</NativeSelect></label>
  {!projects.length&&(!phone||!homeLoading&&!homeError)&&<p>You need project editing access to a project in a workspace to configure workflows.</p>}
  {scheme&&<fieldset disabled={busy} className="space-y-4">
   <label className="flex items-center gap-2"><input type="checkbox" checked={scheme.enabled} onChange={e=>change({...scheme,enabled:e.target.checked})}/>Enforce allowed transitions</label>
   <label className="block">Work type<NativeSelect aria-label="Work type" loading={phone&&typesLoading} error={phone&&!!typesError} value={workType} onChange={e=>setWorkType(e.target.value)}><option value="">Project default</option>{[...new Set([...types,...Object.keys(scheme.work_type_transitions||{})])].map(t=><option key={t}>{t}</option>)}</NativeSelect></label>
   {workType&&<p className="text-sm">{scheme.work_type_transitions?.[workType]?"This type has its own transitions.":"This type inherits the project default. Editing creates an override."}</p>}
   {workType&&scheme.work_type_transitions?.[workType]&&<Button variant="outline" onClick={()=>{const scopes={...scheme.work_type_transitions};delete scopes[workType];change({...scheme,work_type_transitions:scopes});}}>Use project default for this type</Button>}
   <div className="scheme-rules space-y-3">{transitions.map((r,i)=><MobileDisclosure key={i} maxWidth={480} title={`${i+1}. ${r.source} → ${r.target} · ${(r.approval_user_ids||[]).length} approval steps`} className="scheme-rule-disclosure"><div className="scheme-rule flex flex-wrap items-end gap-3 rounded border p-3">
    <label>From<NativeSelect aria-label={`From status ${i+1}`} value={r.source} onChange={e=>edit(i,{source:e.target.value})}>{statuses.map(s=><option key={s}>{s}</option>)}</NativeSelect></label>
    <label>To<NativeSelect aria-label={`To status ${i+1}`} value={r.target} onChange={e=>edit(i,{target:e.target.value})}>{statuses.map(s=><option key={s}>{s}</option>)}</NativeSelect></label>
    <fieldset className="scheme-required flex flex-wrap gap-3"><legend className="text-sm">Required information</legend>{fields.map(f=><label key={f} className="flex items-center gap-1"><input type="checkbox" checked={r.required_fields.includes(f)} onChange={e=>edit(i,{required_fields:e.target.checked?[...r.required_fields,f]:r.required_fields.filter(x=>x!==f)})}/>{f==="due_date"?"Due date":f==="assignee"?"Assignee":"Description"}</label>)}</fieldset>
    <Button variant="outline" aria-label={`Remove transition ${i+1}`} onClick={()=>changeRules(transitions.filter((_,n)=>n!==i))}>Remove</Button>
    <fieldset className="w-full space-y-2"><legend className="text-sm font-medium">Approval route (in order)</legend>
     {(r.approval_user_ids||[]).map((uid,j)=><div key={j} className="scheme-approver flex flex-wrap items-center gap-2"><label>Step {j+1}<NativeSelect aria-label={`Approver for transition ${i+1} step ${j+1}`} value={uid||""} onChange={e=>edit(i,{approval_user_ids:(r.approval_user_ids||[]).map((id,n)=>n===j?Number(e.target.value):id)})}><option value="">Choose a reviewer</option>{people.map(p=><option key={p.id} value={p.id}>{p.name||p.email||`Person ${p.id}`}</option>)}</NativeSelect></label><Button variant="outline" aria-label={`Remove approval step ${j+1} from transition ${i+1}`} onClick={()=>edit(i,{approval_user_ids:(r.approval_user_ids||[]).filter((_,n)=>n!==j)})}>Remove approval step</Button></div>)}
     <Button variant="outline" disabled={(r.approval_user_ids||[]).length>=10} onClick={()=>edit(i,{approval_user_ids:[...r.approval_user_ids||[],0]})}>Add approval step</Button>
     <p className="text-xs text-muted-foreground">No steps means no approval is required. Reviewers must have active project access and cannot approve their own requests.</p>
    </fieldset>
   </div></MobileDisclosure>)}</div>
   <div className="scheme-actions flex flex-wrap gap-2"><Button variant="outline" disabled={transitions.length>=30} onClick={()=>changeRules([...transitions,{source:"To Do",target:"In Progress",required_fields:[]}])}>Add transition</Button><Button disabled={!dirty} onClick={()=>void save()}>Save workflow</Button><Button variant="outline" disabled={!dirty} onClick={discard}>Discard changes and reload</Button></div>
   {dirty&&<p role="status" className="text-sm">Unsaved changes. Save or discard before choosing another project.</p>}
  </fieldset>}
 </main>;
}
