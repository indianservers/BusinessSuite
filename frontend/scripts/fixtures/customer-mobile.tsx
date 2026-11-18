import React,{useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {CompanyQuickCreate} from '@/shared/master-data/CompanyEditor';
import {useAuthStore} from '@/store/authStore';
import {installFormDefaults} from '@/lib/form-defaults';
import '@/index.css';
sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch','1');
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'qa-token',user:{id:77,name:'Demo admin',email:'qa@example.invalid',role:'admin',is_superuser:true,access:{companyId:1,managed:false,isAccessAdmin:true,isGlobalAdmin:true,grants:{srm:{enabled:true,actions:['view','create','edit'],permissions:['srm_manage']},crm:{enabled:true,actions:['view','create','edit'],permissions:['crm_manage']}},memberships:[1],modules:[]}}} as never);
installFormDefaults({values:{timezone:'Asia/Kolkata',currency:'INR',country:'IN',phone_country_code:'+91'},modules:{},companyId:1,branchId:1});
function Fixture(){const [open,setOpen]=useState(true);return <main style={{height:'100dvh',overflow:'hidden'}}><button onClick={()=>setOpen(true)}>Open customer</button>{open&&<CompanyQuickCreate source="srm" roles={['Customer']} recordLabel="Customer" onClose={()=>setOpen(false)} onSaved={(_,keep)=>{if(!keep)setOpen(false);}}/>}</main>}
createRoot(document.getElementById('root')!).render(<BrowserRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}})}><Fixture/></QueryClientProvider></BrowserRouter>);
