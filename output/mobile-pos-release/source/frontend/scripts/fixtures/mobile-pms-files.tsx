import {api} from "@/services/api";
import {refreshPageData} from "@/lib/page-refresh";
import {QueryClient} from "@tanstack/react-query";
import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter,Routes,Route,useNavigate} from "react-router-dom";
import {useAuthStore} from "@/store/authStore";
import Page from "@/apps/project-management/pages/FilesPage";
import "@/index.css";
import "@/apps/project-management/components/ProjectTabs.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:1,email:"qa@example.test",role:"admin",is_superuser:true}});
const created:string[]=[],revoked:string[]=[];const create=URL.createObjectURL.bind(URL),revoke=URL.revokeObjectURL.bind(URL);
URL.createObjectURL=value=>{const url=create(value);created.push(url);return url;};URL.revokeObjectURL=value=>{revoked.push(value);revoke(value);};
Object.assign(window,{filesURLs:()=>({created,revoked}),filesViewer:()=>useAuthStore.setState({user:{...useAuthStore.getState().user,is_superuser:false,access:{managed:true,grants:{project_management:{enabled:true,actions:[],permissions:[]}}}}})});
let settled=0,downloadsSettled=0;
api.interceptors.response.use(response=>{if(response.config.method!=="get")settled++;if(response.config.url?.endsWith("/download"))downloadsSettled++;return response;},error=>{if(error.config?.method!=="get")settled++;if(error.config?.url?.endsWith("/download"))downloadsSettled++;return Promise.reject(error);});
Object.assign(window,{
 filesSettled:()=>settled,filesDownloadsSettled:()=>downloadsSettled,
 filesActor:(id:number)=>useAuthStore.setState({user:{...useAuthStore.getState().user,id}}),
 filesContext:(kind:string,value:string)=>{sessionStorage.setItem("suite-"+kind,value);window.dispatchEvent(new Event(kind==="branch"?"suite:branch-changed":"suite:organization-changed"));}
});
function Harness(){const navigate=useNavigate();Object.assign(window,{filesProject:(id:number)=>navigate("/pms/projects/"+id+"/files")});return <Routes><Route path="/pms/files" element={<Page/>}/><Route path="/pms/projects/:projectId/files" element={<Page/>}/></Routes>;}
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={[location.search.includes("global")?"/pms/files":"/pms/projects/86/files"]}><Harness/></MemoryRouter>);


Object.assign(window,{filesRefresh:()=>refreshPageData(new QueryClient()).catch(()=>undefined)});

let pendingReads=0;const readOptions:{url:string;cache:unknown;cacheControl:unknown}[]=[];
const isSource=(url:string)=>/\/(files|file-folders|projects)$/.test(url.split("?")[0]);
api.interceptors.request.use(config=>{if(config.method==="get"&&isSource(config.url||"")){pendingReads++;readOptions.push({url:config.url||"",cache:config.recordCache,cacheControl:config.headers.get("Cache-Control")});}return config;});
api.interceptors.response.use(response=>{if(response.config.method==="get"&&isSource(response.config.url||""))pendingReads--;return response;},error=>{if(error.config?.method==="get"&&isSource(error.config?.url||""))pendingReads--;return Promise.reject(error);});
Object.assign(window,{filesReadOptions:()=>readOptions,filesPendingReads:()=>pendingReads});
