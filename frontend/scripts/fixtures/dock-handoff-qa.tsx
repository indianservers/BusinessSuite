import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter,useLocation} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import MobileModuleDock from '@/components/layout/MobileModuleDock';
import {SmartCreateModal} from '@/shared/creation/SmartCreateModal';
import {useCreateIntent} from '@/hooks/use-create-intent';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
const module=new URLSearchParams(location.search).get('module')||'crm';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:55,email:'handoff@example.test',employee_id:new URLSearchParams(location.search).has('noemployee')?undefined:7,role:'admin',is_superuser:true}});
(window as any).handoffClosed=0;(window as any).handoffEvents=[];document.addEventListener('focusin',event=>{const el=event.target as HTMLElement;(window as any).handoffEvents.push(el.getAttribute('aria-label')||el.tagName);});
function App(){const route=useLocation(),[open,setOpen]=useState(false);useCreateIntent(kind=>{if(kind==='leads'||kind==='leave')setOpen(true)});useEffect(()=>{if(route.pathname==='/pms/tasks/new')setOpen(true)},[route.pathname]);
 const title=module==='crm'?'Create lead':module==='pms'?'Create task':'Apply leave';
 return <><main id="suite-main"><h1>Handoff source</h1><output>{route.pathname+route.search}</output></main><MobileModuleDock/>{open&&<SmartCreateModal definition={{entity:module==='pms'?'task':module==='crm'?'lead':'leave',title,presentation:'page',size:'standard'}} onClose={()=>{(window as any).handoffClosed++;setOpen(false)}}><form onSubmit={event=>event.preventDefault()}><label>Draft name<input autoFocus aria-label="Draft name"/></label><button type="submit">Save draft</button></form></SmartCreateModal>}</>;
}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[module==='crm'?'/crm/leads':module==='pms'?'/pms/tasks':'/hrms/leave']}><App/></MemoryRouter></QueryClientProvider>);
