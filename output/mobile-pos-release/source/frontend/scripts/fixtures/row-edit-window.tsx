import React,{useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {BrowserRouter,Link,Route,Routes,useNavigate,useParams} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {SmartCreationProvider} from "@/shared/creation/SmartCreationProvider";
import {ActionToolbar} from "@/components/actions";
import {useAuthStore} from "@/store/authStore";
import {api} from "@/services/api";
import {recordSavedEvent} from "@/lib/record-changes";
import "@/index.css";
const module=location.pathname.split('/')[1],resource=({pms:'tasks',crm:'leads',hrms:'employees',srm:'customers',fam:'expenses','power-apps':'applications'} as Record<string,string>)[module]||'tasks';
const base=`/${module}/${resource}`;
localStorage.setItem('bos-enabled-modules','hrms,crm,project_management,srm,fam,power_apps');
const keys=['project_management','crm','hrms','srm','fam','power_apps'];
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,email:'qa@example.invalid',role:'admin',is_superuser:false,access:{companyId:1,managed:true,grants:Object.fromEntries(keys.map(key=>[key,{enabled:true,role:'admin',scope:'all',permissions:['power_apps_view'],actions:['view','edit']}])),modules:keys.map(key=>({key,route:key==='project_management'?'/pms':key==='power_apps'?'/power-apps':'/'+key})),isAccessAdmin:true,isGlobalAdmin:false,memberships:[1]}}});
function Editor(){const {id}=useParams();const navigate=useNavigate();const [title,setTitle]=useState('Original '+id);async function save(close:boolean){await api.put(`/qa/${module}/${id}`,{title});if(close)navigate(base);}return <form onSubmit={e=>{e.preventDefault();void save(true);}}><button type="button" data-save-action>Add check</button><label>Record title<input aria-label="Record title" value={title} onChange={e=>setTitle(e.target.value)}/></label><button type="button" onClick={()=>void save(false)}>Background save</button><button type="submit" data-save-action>Save changes</button><button type="button" onClick={()=>navigate(base)}>Cancel</button></form>}
const routes=[{path:`${module}/${resource}/:id${module==='pms'?'/edit':''}`,element:<Editor/>}];
function List(){const navigate=useNavigate();const [filter,setFilter]=useState(''),[selected,setSelected]=useState(false),[title,setTitle]=useState('Original 17');useEffect(()=>{const saved=(e:Event)=>{const data=(e as CustomEvent).detail?.record;if(data?.title)setTitle(data.title)};window.addEventListener(recordSavedEvent,saved);return()=>window.removeEventListener(recordSavedEvent,saved)},[]);return <main id="suite-main"><h1>Rows</h1><input aria-label="List filter" value={filter} onChange={e=>setFilter(e.target.value)}/><input type="checkbox" aria-label="Selected row" checked={selected} onChange={e=>setSelected(e.target.checked)}/><span data-testid="row-title">{title}</span><ActionToolbar actions={[{id:'edit',kind:'edit',label:'Edit row',primary:true,onSelect:()=>navigate(base+'/17')}]}/><Link to={base+'/18'+(module==='pms'?'/edit':'')} aria-label="Direct edit link">Edit another</Link></main>}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><BrowserRouter><SmartCreationProvider routes={routes}><Routes><Route path={`${module}/${resource}`} element={<List/>}/>{routes.map(r=><Route key={r.path} path={r.path} element={r.element}/>)}</Routes></SmartCreationProvider></BrowserRouter></QueryClientProvider>);
