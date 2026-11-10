import {useAuthStore} from "@/store/authStore";
import {api} from "@/services/api";
import {refreshPageData} from "@/lib/page-refresh";
import {QueryClient} from "@tanstack/react-query";
import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter,Routes,Route,useNavigate,Link} from "react-router-dom";
import Page from "@/apps/project-management/pages/MilestonesPage";
import "@/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:1,email:"qa@example.test",role:"admin",is_superuser:true}});
let settled=0;
api.interceptors.response.use(response=>{if(response.config.method!=="get")settled++;return response;},error=>{if(error.config?.method!=="get")settled++;return Promise.reject(error);});
Object.assign(window,{
 milestoneSettled:()=>settled,
 milestoneActor:(id:number)=>useAuthStore.setState({user:{...useAuthStore.getState().user,id}}),
 milestoneContext:(kind:string,value:string)=>{sessionStorage.setItem("suite-"+kind,value);window.dispatchEvent(new Event(kind==="branch"?"suite:branch-changed":"suite:organization-changed"));}
});
function Harness(){
 const navigate=useNavigate();Object.assign(window,{milestoneProject:(id:number)=>navigate("/pms/projects/"+id+"/milestones")});
 return <><Routes><Route path="/pms/projects/:projectId/milestones" element={<Page/>}/></Routes><Link to="/pms/projects/87/milestones">Project 87</Link><Link to="/pms/projects/86/milestones">Project 86</Link></>;
}
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/pms/projects/86/milestones"]}><Harness/></MemoryRouter>);


Object.assign(window,{milestoneRefresh:()=>refreshPageData(new QueryClient()).catch(()=>undefined)});
