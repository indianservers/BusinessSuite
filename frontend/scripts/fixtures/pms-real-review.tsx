// No Axios adapter: every suite read/write goes to the disposable FastAPI bridge.
import {createRoot} from "react-dom/client";
import {useState} from "react";
import {BrowserRouter,Navigate,Route,Routes,Link,useLocation} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import AppLayout from "../../src/components/layout/AppLayout";
import TaskDetail from "../../src/apps/project-management/pages/TaskDetail";
import WorkspacesPage from "../../src/apps/project-management/pages/WorkspacesPage";
import {useAuthStore,type AuthUser} from "../../src/store/authStore";
import "../../src/index.css";

if(!import.meta.env.DEV||!["127.0.0.1","localhost"].includes(location.hostname))throw new Error("Loopback development review only");
type Bootstrap={token:string;user:AuthUser;company:number;branch:number;workspace:number;project:number;tasks:number[];role:string;other_workspace?:number|null};
function ReviewRoute(){const location=useLocation();return <output aria-label="Review route">{location.pathname}</output>;}
function ReviewReadFault({taskId}:{taskId:number}){
 const [notice,setNotice]=useState("");
 return <><button type="button" className="block underline" onClick={async()=>{const response=await fetch(`/api/_qa/fail-next-status-read?task=${taskId}`,{method:"POST"});setNotice(response.ok?`Next status read for task ${taskId} will fail`:"Could not arm local read fault");}}>Fail next task {taskId} status read</button><output>{notice}</output></>;
}
function ReviewIdentity({initialRole}:{initialRole:string}){
 const [role,setRole]=useState(initialRole),[busy,setBusy]=useState(false),[error,setError]=useState("");
 return <label>Review identity<select aria-label="Review identity" value={role} disabled={busy} onChange={async event=>{
  const next=event.target.value;setBusy(true);setError("");
  try{const response=await fetch(`/api/_qa/bootstrap?role=${encodeURIComponent(next)}`,{cache:"no-store"});if(!response.ok)throw new Error("Could not load disposable identity");const data:Bootstrap=await response.json();
   sessionStorage.setItem("suite-organization",String(data.company));sessionStorage.setItem("suite-branch",String(data.branch));
   useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:data.token,user:data.user});setRole(data.role);
  }catch{setError("Could not switch disposable identity");}finally{setBusy(false);}
 }}>{["member","guest","reviewer","owner"].map(value=><option key={value}>{value}</option>)}</select>{error&&<span role="alert">{error}</span>}</label>;
}
async function start(){
 const role=new URLSearchParams(location.search).get("role")||"member";
 const response=await fetch(`/api/_qa/bootstrap?role=${encodeURIComponent(role)}`,{cache:"no-store"});
 if(!response.ok)throw new Error("Disposable review bridge is unavailable");
 const data:Bootstrap=await response.json();
 sessionStorage.setItem("suite-organization",String(data.company));
 sessionStorage.setItem("suite-branch",String(data.branch));
 useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:data.token,user:data.user});
 const selected=Number(new URLSearchParams(location.search).get("task"))||data.tasks[0];
 const initialHref=new URLSearchParams(location.search).get("start")==="workspace"?`/pms?workspace=${data.workspace}`:`/pms/tasks/${selected}`;
 createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><BrowserRouter>
  <aside aria-label="Disposable API review controls" className="fixed bottom-20 right-3 z-[99999] max-w-60 rounded border bg-background p-2 text-xs"><details><summary>Review controls</summary><p>Disposable API review</p><ReviewIdentity initialRole={data.role}/><ReviewReadFault taskId={data.tasks[2]}/><ReviewRoute/><Link className="block underline" to={`/pms?workspace=${data.workspace}`}>Open review workspace</Link>{data.other_workspace&&<Link className="block underline" to={`/pms?workspace=${data.other_workspace}`}>Open alternate review workspace</Link>}{data.tasks.map((id,index)=><Link key={id} className="block underline" to={`/pms/tasks/${id}`}>Review task {index+1}</Link>)}<p>Real API; isolated test records only.</p></details></aside>
  <Routes><Route path="/pms-real-review-qa.html" element={<Navigate replace to={initialHref}/>}/><Route element={<AppLayout/>}><Route path="/pms" element={<WorkspacesPage/>}/><Route path="/pms/tasks/:taskId" element={<TaskDetail/>}/><Route path="/pms/tasks" element={<p>Use Open review workspace to return to the disposable collection.</p>}/></Route></Routes>
 </BrowserRouter></QueryClientProvider>);
}
void start().catch(error=>{document.getElementById("root")!.textContent=error instanceof Error?error.message:"Review initialization failed";});
