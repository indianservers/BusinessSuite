import React from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter,Routes,Route,useNavigate} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import CatalogPage from '@/shared/catalog/CatalogPage';
import SRMPOSPage from '@/apps/srm/pages/SRMPOSPage';
import FAMWorkspacePage from '@/apps/fam/FAMWorkspacePage';
import {useAuthStore} from '@/store/authStore';
import {api} from '@/services/api';
import {setPackContext} from '@/lib/pack-context';
import {Toaster} from '@/components/ui/toaster';
import '@/index.css';
const qa=window as typeof window&{qaAuth:{token:string;branch:string;context:string;implicit?:boolean};qaApi:typeof api;qaNavigate:ReturnType<typeof useNavigate>};
sessionStorage.removeItem('suite-tenant');sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch',qa.qaAuth.branch);if(!qa.qaAuth.implicit)setPackContext(qa.qaAuth.context);
useAuthStore.setState({isHydrated:false,isAuthenticated:true,accessToken:qa.qaAuth.token,user:null});qa.qaApi=api;
function Harness(){qa.qaNavigate=useNavigate();return <Routes><Route path="catalog-service" element={<CatalogPage source="srm"/>}/><Route path="srm/pos" element={<SRMPOSPage/>}/><Route path="srm/inventory/batches" element={<FAMWorkspacePage kind="inventoryBatches"/>}/><Route path="fam/inventory/batches" element={<FAMWorkspacePage kind="inventoryBatches"/>}/></Routes>;}
async function mount(){const [identity,access]=await Promise.all([api.get('/auth/me',{recordCache:false}),api.get('/access/me',{recordCache:false})]);const role=typeof identity.data.role==='string'?identity.data.role:identity.data.role?.name||null;useAuthStore.setState({isHydrated:true,user:{...identity.data,role,primary_role:role,access:access.data}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><Harness/><Toaster/></BrowserRouter></QueryClientProvider>);}
void mount();
