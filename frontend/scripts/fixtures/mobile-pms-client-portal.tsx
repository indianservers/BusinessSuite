import {useAuthStore} from "@/store/authStore";
import {api} from "@/services/api";
import {refreshPageData} from "@/lib/page-refresh";
import {QueryClient} from "@tanstack/react-query";
import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import Page from "@/apps/project-management/pages/ClientPortalPage";
import "@/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:1,email:"qa@example.test",role:"admin",is_superuser:true}});
let settled=0;
api.interceptors.response.use(response=>{if(response.config.method!=="get")settled++;return response;},error=>{if(error.config?.method!=="get")settled++;return Promise.reject(error);});
Object.assign(window,{
 portalSettled:()=>settled,
 portalActor:(id:number)=>useAuthStore.setState({user:{...useAuthStore.getState().user,id}}),
 portalContext:(kind:string,value:string)=>{sessionStorage.setItem("suite-"+kind,value);window.dispatchEvent(new Event(kind==="branch"?"suite:branch-changed":"suite:organization-changed"));}
});
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/pms/client-portal"]}><Page/></MemoryRouter>);

(window as unknown as {refreshPortal:()=>Promise<void>}).refreshPortal=()=>refreshPageData(new QueryClient());
