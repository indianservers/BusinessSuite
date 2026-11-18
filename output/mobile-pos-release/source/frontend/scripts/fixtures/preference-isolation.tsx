import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SharedDataGrid from "../../src/shared/data-grid/SharedDataGrid";
import { localGridSource } from "../../src/shared/data-grid/local-source";
import { emptyQuery, type GridColumn } from "../../src/shared/data-grid/types";
import { defaultLayout } from "../../src/shared/data-grid/state";
import { WorkspaceWork } from "../../src/apps/project-management/pages/WorkspaceWork";
import type { WorkTask } from "../../src/apps/project-management/pages/workspaceTypes";
import { api } from "../../src/services/api";
import { useAuthStore } from "../../src/store/authStore";
import "../../src/index.css";
import "../../src/design-system/premium.css";
import "../../src/shared/data-grid/suite-list-surface.css";
import "../../src/apps/project-management/pages/WorkspaceBoardChrome.css";

if(!import.meta.env.DEV||!["localhost","127.0.0.1"].includes(location.hostname))throw new Error("Loopback development fixture only");
const company=88800, first=88801, second=88802, workspace=77;
const fakeUser=(id:number)=>({id,email:`fixture-${id}@example.test`,role:"admin",is_superuser:true,access:{companyId:company,companyName:"DISPOSABLE PREFERENCE FIXTURE",managed:false,modules:[],grants:{},organizations:[],memberships:[],isAccessAdmin:true,isGlobalAdmin:true}});
useAuthStore.setState({user:fakeUser(first),isAuthenticated:true,isHydrated:true,accessToken:"fixture"});
// These component checks have no external network, provider connection or business writes.
api.defaults.adapter=async config=>{if((config.method||"get").toLowerCase()!=="get"&&!config.readOnlyPreview)throw new Error("Fixture writes disabled");return {data:{records:{}},status:200,statusText:"OK",headers:{},config};};
const tasks:WorkTask[]=[{id:1,project_id:1,task_key:"QA-1",title:"High fixture task",status:"To Do",priority:"High",position:0,comments_count:0},{id:2,project_id:1,task_key:"QA-2",title:"Low fixture task",status:"To Do",priority:"Low",position:1,comments_count:0}];
const columns:GridColumn<WorkTask>[]=[{id:"title",title:"Task"},{id:"status",title:"Status",type:"status"},{id:"priority",title:"Priority"}];
const pms=new URLSearchParams(location.search).has("pms");
function Fixture(){
  const user=useAuthStore(s=>s.user)!;
  const [violations,setViolations]=useState(0),[revision,setRevision]=useState(0),[query,setQuery]=useState(""),[project,setProject]=useState(""),[assignee,setAssignee]=useState(""),[view,setView]=useState<"list"|"board"|"people"|"calendar"|"workload"|"activity">("list"),[notice,setNotice]=useState("");
  const switchUser=()=>useAuthStore.setState({user:fakeUser(useAuthStore.getState().user?.id===first?second:first)});
  useEffect(()=>{const key=(event:KeyboardEvent)=>{if(event.key==="F8"){event.preventDefault();switchUser();}};window.addEventListener("keydown",key);return()=>window.removeEventListener("keydown",key);},[]);
  // Inspect the committed DOM before passive preference-reset effects can mask a leak.
  useLayoutEffect(()=>{if(user.id===second&&Array.from(document.querySelectorAll('.udg-view-option')).some(el=>el.textContent?.includes("Private A layout")))setViolations(v=>v+1);},[user.id]);
  const source=useMemo(()=>{const base=localGridSource("preference-fixture",tasks,columns,r=>String(r.id));return {...base,load:async(...args:Parameters<typeof base.load>)=>({...await base.load(...args),permissions:{edit:false,export:false,assign:false}})};},[]);
  function seedLegacy(){
    const id=pms?`pms-workspace-work-${workspace}`:"preference-isolation";
    const layout=defaultLayout(columns);
    localStorage.setItem(`suite-grid:v1:${company}:${user.id}:organization:${id}`,JSON.stringify({layout,query:emptyQuery(),businessGrouping:true,views:[{id:"legacy",name:"Legacy table layout",layout,query:emptyQuery()}]}));
    if(pms)localStorage.setItem(`pms-board-view-${user.id}-${company}-${workspace}`,JSON.stringify({query:"Low",projectFilter:"1",assigneeFilter:"",priority:"Low",status:"",workType:"",focus:"all"}));
    setRevision(v=>v+1);
  }
  function seedDamaged(){
    const id=pms?`pms-workspace-work-${workspace}`:"preference-isolation";
    localStorage.setItem(`suite-grid:v1:${company}:${user.id}:organization:${id}`,"{invalid");
    if(pms)localStorage.setItem(`pms-board-view-${user.id}-${company}-${workspace}`,"{invalid");
    setRevision(v=>v+1);
  }
  return <main className="wb-reference p-3"><header className="mb-3 flex flex-wrap items-center gap-3"><h1>Disposable preference fixture</h1><strong>Account {user.id===first?"A":"B"}</strong><button type="button" onClick={switchUser}>Switch fixture account (F8)</button><button type="button" onClick={seedLegacy}>Seed older-format preferences</button><button type="button" onClick={seedDamaged}>Seed damaged preferences</button><output aria-label="Cross-user preference exposures">{violations}</output></header><p>F8 switches the fixture identity without closing an open saved-view menu. No real account is changed.</p><p role="status">{notice}</p>{pms?<WorkspaceWork key={`${user.id}:${company}:${revision}`} tasks={tasks} members={[]} projects={[{id:1,name:"Fixture project",project_key:"FIX"}]} workspaceId={workspace} query={query} onQueryChange={setQuery} onClearSearch={()=>setQuery("")} projectFilter={project} setProjectFilter={setProject} assigneeFilter={assignee} setAssigneeFilter={setAssignee} view={view} onViewChange={setView} canEdit={false} updateTask={async()=>false} onOpen={()=>{}} onRefresh={async()=>{}} onError={setNotice} onNotice={setNotice} renderMemberActions={()=>null}/>:<SharedDataGrid key={revision} gridId="preference-isolation" columns={columns} dataSource={source} getRowId={r=>String(r.id)}/>}</main>;
}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><MemoryRouter initialEntries={[pms?"/pms":"/crm/deals"]}><Fixture/></MemoryRouter></QueryClientProvider>);
