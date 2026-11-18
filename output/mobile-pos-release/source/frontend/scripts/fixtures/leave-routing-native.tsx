import React from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter,Routes,Route,useNavigate} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import LeavePage from '@/apps/hrms/pages/leave/LeavePage';
import {useAuthStore} from '@/store/authStore';
import {api} from '@/services/api';
import {setPackContext} from '@/lib/pack-context';
import {Toaster} from '@/components/ui/toaster';
import '@/index.css';
const qa=window as typeof window&{qaAuth:{token:string;branch:string;context:string};qaApi:typeof api;qaNavigate:ReturnType<typeof useNavigate>};
sessionStorage.removeItem('suite-tenant');sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch',qa.qaAuth.branch);setPackContext(qa.qaAuth.context);
useAuthStore.setState({isHydrated:false,isAuthenticated:true,accessToken:qa.qaAuth.token,user:null});qa.qaApi=api;
function Harness(){qa.qaNavigate=useNavigate();return <Routes><Route path="hrms/leave" element={<main style={{padding:12}}><LeavePage/></main>}/></Routes>;}
async function mount(){const [identity,access]=await Promise.all([api.get('/auth/me',{recordCache:false}),api.get('/access/me',{recordCache:false})]);const role=typeof identity.data.role==='string'?identity.data.role:identity.data.role?.name||null;useAuthStore.setState({isHydrated:true,user:{...identity.data,role,primary_role:role,access:access.data}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><Harness/><Toaster/></BrowserRouter></QueryClientProvider>);}
void mount();
