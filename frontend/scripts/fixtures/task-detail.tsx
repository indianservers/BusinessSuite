// Actual TaskDetail with an in-memory task. No API/provider requests leave this adapter.
import {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {AxiosError} from "axios";
import AppLayout from "../../src/components/layout/AppLayout";
import TaskDetail from "../../src/apps/project-management/pages/TaskDetail";
import {api} from "../../src/services/api";
import {useAuthStore} from "../../src/store/authStore";
import "../../src/index.css";
import "../../src/design-system/premium.css";

if(!import.meta.env.DEV||!["localhost","127.0.0.1"].includes(location.hostname))throw new Error("Loopback development fixture only");
const taskId=88601,projectId=88602,userId=88603;
let rejectSaves=true,attempts=0;
let task={id:taskId,project_id:projectId,task_key:"FIX-1",title:"Disposable recovery task",description:"Fixture description",status:"To Do",priority:"High",work_type:"Task",assignee_user_ids:[],reporter_user_id:userId,estimated_hours:2,story_points:0,position:0,created_at:"2026-11-11T00:00:00Z",updated_at:"2026-11-11T00:00:00Z"};
// No token means the task realtime hook cannot open a socket or publish presence.
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:null,user:{id:userId,email:"task-recovery@example.test",role:"admin",is_superuser:true,access:{companyId:88600,companyName:"DISPOSABLE TASK FIXTURE",managed:false,modules:[],grants:{},organizations:[],memberships:[],isAccessAdmin:true,isGlobalAdmin:true}}});
const notify=()=>window.dispatchEvent(new Event("qa:task-recovery"));
function Controls(){
 const [failure,setFailure]=useState(true),[saved,setSaved]=useState(task.title),[count,setCount]=useState(0);
 useEffect(()=>{const changed=()=>{setSaved(task.title);setCount(attempts);};window.addEventListener("qa:task-recovery",changed);return()=>window.removeEventListener("qa:task-recovery",changed);},[]);
 return <aside aria-label="Disposable task recovery controls" style={{position:"fixed",right:12,bottom:80,zIndex:99999,maxWidth:290,background:"white",padding:12,border:"1px solid"}}><button type="button" onClick={()=>{rejectSaves=!failure;setFailure(!failure);}}>{failure?"Allow task saves":"Fail task saves"}</button><p>Fixture save attempts: {count}</p><output aria-label="Fixture persisted title">{saved}</output><p>In-memory task only; no business data is written.</p></aside>;
}
api.defaults.adapter=async config=>{
 const path=new URL(config.url||"/","http://fixture.invalid").pathname,method=(config.method||"get").toLowerCase();
 let data:unknown=[];
 if(method==="patch"&&path===`/project-management/tasks/${taskId}`){
  attempts++;notify();
  if(rejectSaves)throw new AxiosError("Disposable task save rejected","ERR_BAD_REQUEST",config,undefined,{data:{detail:"Fixture save failed. Your draft should remain available."},status:422,statusText:"Unprocessable Entity",headers:{},config});
  const changes=typeof config.data==="string"?JSON.parse(config.data):config.data;
  task={...task,...changes};data={...task};notify();
 }else if(!["get","head","options"].includes(method)&&!config.readOnlyPreview){
  throw new AxiosError("Fixture write disabled","ERR_BAD_REQUEST",config,undefined,{data:{detail:"Only the disposable task save is supported"},status:403,statusText:"Forbidden",headers:{},config});
 }else if(path===`/project-management/tasks/${taskId}`)data={...task};
 else if(path.endsWith("/transition-approvals"))data={can_request:false,transitions:[],requests:[]};
 else if(path===`/project-management/projects/${projectId}`)data={id:projectId,name:"Recovery fixture project",project_key:"FIX",can_manage_tasks:true,status:"Active"};
 else if(path.includes("/custom-fields"))data={fields:[],can_edit:true};
 else if(path===`/project-management/management/tasks/${taskId}`)data={id:taskId,title:task.title,project_id:projectId,status:task.status,can_edit:false,execution:{revision:1,blocked_reason:"",responsible_user_id:null,review_date:null,evidence_required:false,evidence:""},completion:{checklist:[],subtasks:[],blockers:[]},note_sources:[]};
 else if(path.endsWith("/assignment-options"))data={items:[],can_add_existing:false,workspace_id:1};
 else if(path.endsWith("/branches/context"))data={selected:1,branches:[{id:1,name:"DISPOSABLE FIXTURE",can_write:true}]};
 else if(path.endsWith("/access/setup"))data={companyId:88600,ready:true,items:[]};
 else if(path.endsWith("/access/settings/defaults/effective"))data={values:{},modules:{}};
 else if(path.includes("notifications"))data={items:[],unread:0,total:0};
 return {data,status:200,statusText:"OK",headers:{},config};
};
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><MemoryRouter initialEntries={[`/pms/tasks/${taskId}`]}><Controls/><Routes><Route element={<AppLayout/>}><Route path="/pms/tasks/:taskId" element={<TaskDetail/>}/></Route></Routes></MemoryRouter></QueryClientProvider>);
