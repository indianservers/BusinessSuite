import {Toaster} from "@/components/ui/toaster";
import React from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter,Routes,Route,useNavigate} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import CommonEntityPage from '@/common/CommonEntityPage';
import AnalyticsPage from '@/apps/project-management/pages/AnalyticsPage';
import {crmRoutes} from '@/apps/crm/routes';
import {srmRoutes} from '@/apps/srm/routes';
import {hrmsRoutes} from '@/apps/hrms/routes';
import {projectManagementRoutes} from '@/apps/project-management/routes';
import {famRoutes} from '@/apps/fam/routes';
import {useAuthStore} from '@/store/authStore';
import {api} from '@/services/api';
import '../../src/index.css';

const harness = window as typeof window & {qaAuth:{token:string;user_id:number;branch:string};qaApi:typeof api;qaNavigate:ReturnType<typeof useNavigate>};
const auth=harness.qaAuth;
sessionStorage.setItem('suite-organization','1');
sessionStorage.setItem('suite-branch',auth.branch);
useAuthStore.setState({isHydrated:false,isAuthenticated:true,accessToken:auth.token,user:null});
harness.qaApi=api;
const routes=[...crmRoutes,...srmRoutes,...hrmsRoutes,...projectManagementRoutes,...famRoutes];
function Harness(){harness.qaNavigate=useNavigate();return <Routes><Route path="common/:entity" element={<CommonEntityPage routes={routes}/>}/><Route path="srm/pos" element={srmRoutes.find(route=>route.path==='srm/pos')?.element}/><Route path="qa/analytics" element={<AnalyticsPage mode="team"/>}/></Routes>}
async function mount(){
 const [identity,access]=await Promise.all([api.get('/auth/me',{recordCache:false}),api.get('/access/me',{recordCache:false})]);
 const role=typeof identity.data.role === "string" ? identity.data.role : identity.data.role?.name || null;
 useAuthStore.setState({isHydrated:true,user:{...identity.data,role,primary_role:role,access:access.data}});
 createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><React.Suspense fallback={<p role="status">Loading native page...</p>}><Harness/><Toaster/></React.Suspense></BrowserRouter></QueryClientProvider>);

}
void mount();
