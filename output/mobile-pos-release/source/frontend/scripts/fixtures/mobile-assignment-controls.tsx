import React from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter,MemoryRouter,Routes,Route,Link} from "react-router-dom";
import {QueryClient,QueryClientProvider,onlineManager} from "@tanstack/react-query";
import Page from "@/apps/project-management/pages/AssignmentControlsPage";
import {useAuthStore} from "@/store/authStore";
import "@/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:1,email:"qa@example.test",role:"admin",is_superuser:true}});
onlineManager.setOnline(!new URLSearchParams(location.search).has("offline"));
const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
Object.assign(window,{__controlOnline:(online:boolean)=>onlineManager.setOnline(online),__controlFetching:()=>client.isFetching(),__controlActor:(id:number)=>useAuthStore.setState({user:{...useAuthStore.getState().user,id}}),__controlRead:(kind:string,project?:string)=>client.refetchQueries({queryKey:kind==="tasks"?["assignment-control-tasks",project]:[kind==="projects"?"assignment-control-options":"assignment-control-people"],type:"active"}).catch(()=>undefined)});
const navigation=new URLSearchParams(location.search).has("navigation");
function Surface(){return <>{navigation&&<nav aria-label="Fixture navigation"><Link to="/control-destination">Leave controls</Link><a href={location.pathname+location.search+"#control-inputs"}>Same-page anchor</a><a href="/control-document">Document destination</a></nav>}<Routes><Route path={navigation?"/control-qa":"/pms/assignment-controls"} element={<Page/>}/><Route path="*" element={<p>Assignment controls destination</p>}/></Routes></>;}
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}>{navigation?<BrowserRouter><Surface/></BrowserRouter>:<MemoryRouter initialEntries={["/pms/assignment-controls"]}><Surface/></MemoryRouter>}</QueryClientProvider>);
