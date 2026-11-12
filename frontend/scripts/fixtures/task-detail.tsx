// Actual TaskDetail with an in-memory task. No API/provider requests leave this adapter.
import {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {AxiosError} from "axios";
import AppLayout from "../../src/components/layout/AppLayout";
import TaskDetail from "../../src/apps/project-management/pages/TaskDetail";
import {TaskDrawer} from "../../src/apps/project-management/pages/WorkspaceWork";
import type {WorkTask} from "../../src/apps/project-management/pages/workspaceTypes";
import "../../src/apps/project-management/pages/workspaces.css";
import "../../src/apps/project-management/pages/WorkspaceBoardChrome.css";
import {api} from "../../src/services/api";
import {useAuthStore} from "../../src/store/authStore";
import {recordSavedEvent} from "../../src/lib/record-changes";
import "../../src/index.css";
import "../../src/design-system/premium.css";

if(!import.meta.env.DEV||!["localhost","127.0.0.1"].includes(location.hostname))throw new Error("Loopback development fixture only");
const taskId=new URLSearchParams(location.search).has("loadFailure")?88611:88601,projectId=88602,userId=88603;
const readOnly=new URLSearchParams(location.search).has("readOnly");
let rejectSaves=!new URLSearchParams(location.search).has("conflict"),attempts=0,editRevision=0;
let fixtureComments:unknown[]=[];
let rejectReads=new URLSearchParams(location.search).has("loadFailure");
let task={id:taskId,project_id:projectId,task_key:"FIX-1",title:"Disposable recovery task",description:"Fixture description",status:"To Do",priority:"High",work_type:"Task",assignee_user_ids:[],reporter_user_id:userId,estimated_hours:2,story_points:0,position:0,created_at:"2026-11-11T00:00:00Z",updated_at:"2026-11-11T00:00:00Z"};
// No token means the task realtime hook cannot open a socket or publish presence.
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:null,user:{id:userId,email:"task-recovery@example.test",role:"admin",is_superuser:true,access:{companyId:88600,companyName:"DISPOSABLE TASK FIXTURE",managed:false,modules:[],grants:{},organizations:[],memberships:[],isAccessAdmin:true,isGlobalAdmin:true}}});
const notify=()=>window.dispatchEvent(new Event("qa:task-recovery"));
function remoteEdit(){task={...task,title:`Other editor revision ${++editRevision}`,updated_at:new Date(Date.UTC(2026,10,12,12,0,editRevision)).toISOString()};notify();}
function Controls(){
 const [failure,setFailure]=useState(rejectSaves),[readFailure,setReadFailure]=useState(rejectReads),[saved,setSaved]=useState(task.title),[savedEstimate,setSavedEstimate]=useState(task.estimated_hours),[count,setCount]=useState(0);
 useEffect(()=>{const changed=()=>{setSaved(task.title);setSavedEstimate(task.estimated_hours);setCount(attempts);};window.addEventListener("qa:task-recovery",changed);return()=>window.removeEventListener("qa:task-recovery",changed);},[]);
 useEffect(()=>{const simulate=(event:KeyboardEvent)=>{if(event.key!=="F6")return;event.preventDefault();remoteEdit();window.dispatchEvent(new CustomEvent(recordSavedEvent,{detail:{url:`/project-management/tasks/${taskId}`,method:"patch",record:task}}));};window.addEventListener("keydown",simulate);return()=>window.removeEventListener("keydown",simulate);},[]);
 return <aside aria-label="Disposable task recovery controls" style={{position:"fixed",right:12,bottom:80,zIndex:99999,maxWidth:290,background:"white",padding:12,border:"1px solid"}}><button type="button" onClick={()=>{rejectSaves=!failure;setFailure(!failure);}}>{failure?"Allow task saves":"Fail task saves"}</button><button type="button" onClick={()=>{rejectReads=!readFailure;setReadFailure(!readFailure);}}>{readFailure?"Allow task reads":"Fail task reads"}</button><button type="button" onClick={()=>{task={...task,title:`Other editor revision ${++editRevision}`,updated_at:new Date(Date.UTC(2026,10,12,12,0,editRevision)).toISOString()};notify();}}>Simulate another editor</button><p>Fixture save attempts: {count}</p><output aria-label="Fixture persisted title">{saved}</output><output aria-label="Fixture persisted estimate">{savedEstimate}</output><p>In-memory task only; no business data is written.</p></aside>;
}
api.defaults.adapter=async config=>{
 const path=new URL(config.url||"/","http://fixture.invalid").pathname,method=(config.method||"get").toLowerCase();
 let data:unknown=[];
 if(method==="post"&&path===`/project-management/tasks/${taskId}/comments`){
  if(readOnly||rejectSaves)throw new AxiosError("Disposable comment save rejected","ERR_BAD_REQUEST",config,undefined,{data:{detail:"Fixture comment failed. Retain the draft and retry."},status:403,statusText:"Forbidden",headers:{},config});
  const changes=typeof config.data==="string"?JSON.parse(config.data):config.data;
  data={id:fixtureComments.length+1,author_user_id:userId,created_at:"2026-11-12T10:00:00Z",...changes};fixtureComments.push(data);
 }else if(method==="get"&&path===`/project-management/tasks/${taskId}/comments`){data=fixtureComments;}
 else if(method==="patch"&&path===`/project-management/tasks/${taskId}`){
  if(readOnly)throw new AxiosError("Read-only fixture task","ERR_BAD_REQUEST",config,undefined,{data:{detail:"Task updates are not permitted"},status:403,statusText:"Forbidden",headers:{},config});
  attempts++;notify();
  if(rejectSaves)throw new AxiosError("Disposable task save rejected","ERR_BAD_REQUEST",config,undefined,{data:{detail:"Fixture save failed. Your draft should remain available."},status:422,statusText:"Unprocessable Entity",headers:{},config});
  const changes=typeof config.data==="string"?JSON.parse(config.data):config.data;
  if(Object.prototype.hasOwnProperty.call(changes,"expected_updated_at")&&changes.expected_updated_at!==task.updated_at)throw new AxiosError("Stale fixture task","ERR_BAD_REQUEST",config,undefined,{data:{detail:"This task changed while you were editing. Your changes were not saved. Review the latest task before retrying."},status:409,statusText:"Conflict",headers:{},config});
  delete changes.expected_updated_at;
  changes.updated_at=new Date(Date.UTC(2026,10,12,12,0,++editRevision)).toISOString();
  task={...task,...changes};data={...task};notify();
 }else if(!["get","head","options"].includes(method)&&!config.readOnlyPreview){
  throw new AxiosError("Fixture write disabled","ERR_BAD_REQUEST",config,undefined,{data:{detail:"Only the disposable task save is supported"},status:403,statusText:"Forbidden",headers:{},config});
 }else if(path===`/project-management/tasks/${taskId}`){
  if(rejectReads)throw new AxiosError("Disposable task read rejected","ERR_BAD_REQUEST",config,undefined,{data:{detail:"Fixture task could not be loaded."},status:503,statusText:"Unavailable",headers:{},config});
  data={...task};
 }
 else if(path.endsWith("/transition-approvals"))data={can_request:false,transitions:[],requests:[]};
 else if(path==="/project-management/timer")data=null;
 else if(path===`/project-management/projects/${projectId}`)data={id:projectId,name:"Recovery fixture project",project_key:"FIX",can_manage_tasks:!readOnly,status:"Active"};
 else if(path.includes("/custom-fields"))data={fields:[],can_edit:true};
 else if(path===`/project-management/management/tasks/${taskId}`)data={id:taskId,title:task.title,project_id:projectId,status:task.status,can_edit:false,execution:{revision:1,blocked_reason:"",responsible_user_id:null,review_date:null,evidence_required:false,evidence:""},completion:{checklist:[],subtasks:[],blockers:[]},note_sources:[]};
 else if(path.endsWith("/assignment-options"))data={items:[],can_add_existing:false,workspace_id:1};
 else if(path.endsWith("/branches/context"))data={selected:1,branches:[{id:1,name:"DISPOSABLE FIXTURE",can_write:true}]};
 else if(path.endsWith("/access/setup"))data={companyId:88600,ready:true,items:[]};
 else if(path.endsWith("/access/settings/defaults/effective"))data={values:{},modules:{}};
 else if(path.includes("notifications"))data={items:[],unread:0,total:0};
 return {data,status:200,statusText:"OK",headers:{},config};
};
function DrawerFixture(){
 const [record,setRecord]=useState<WorkTask>({...task,comments_count:0}),[open,setOpen]=useState(true),[error,setError]=useState("");
 useEffect(()=>{const refresh=(event:KeyboardEvent)=>{if(event.key==="F8"){event.preventDefault();setRecord(current=>({...current,comments_count:current.comments_count+1}));}if(event.key==="F9"){event.preventDefault();rejectSaves=false;}};window.addEventListener("keydown",refresh);return()=>window.removeEventListener("keydown",refresh);},[]);
 return <><button onClick={()=>setOpen(true)}>Open fixture task</button><button onClick={()=>setRecord(current=>({...current,comments_count:current.comments_count+1}))}>Refresh fixture conversation</button><TaskDrawer task={open?record:undefined} members={[]} canEdit={!readOnly} onClose={()=>setOpen(false)} onUpdate={async(_,changes)=>{setRecord(current=>({...current,...changes}));return true;}} onRefresh={async()=>{setRecord(current=>({...current,comments_count:current.comments_count+1}));}} onError={setError} error={error}/></>;
}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><MemoryRouter initialEntries={[`/pms/tasks/${taskId}`]}><Controls/><Routes><Route element={<AppLayout/>}><Route path="/pms/tasks/:taskId" element={new URLSearchParams(location.search).has("drawer")?<DrawerFixture/>:<TaskDetail/>}/></Route></Routes></MemoryRouter></QueryClientProvider>);
