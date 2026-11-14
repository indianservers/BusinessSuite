/** Development-only component fixture; Playwright supplies the synthetic API. */
import React,{useState} from 'react';
import ReactDOM from 'react-dom/client';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import HelpdeskPage from '../../src/apps/hrms/pages/helpdesk/HelpdeskPage';
import {MemoryRouter} from 'react-router-dom';
import TicketSavedViews,{type TicketView} from '../../src/apps/hrms/pages/helpdesk/TicketSavedViews';
import {useAuthStore} from '../../src/store/authStore';
import '../../src/index.css';
if(!import.meta.env.DEV)throw Error('Development fixture only');
useAuthStore.setState({isAuthenticated:true,isHydrated:true,token:'synthetic-browser-fixture',user:{id:7,email:'views-fixture@example.com',role:'Super Admin',is_superuser:true,access:{companyId:1} as any}} as any);
function Demo(){const [scope,setScope]=useState('7:1');const [filters,setFilters]=useState<TicketView>({status:'Pending',priority:'Critical',assigned_to_me:true,my_tickets:false});
 return <main style={{maxWidth:900,padding:24}}><h1>HRMS ticket view QA</h1><button type="button" onClick={()=>{setScope('7:2');useAuthStore.setState(s=>({user:{...s.user!,access:{...s.user?.access,companyId:2} as any}}))}}>Switch fixture company</button><TicketSavedViews key={scope} scope={scope} filters={filters} onApply={setFilters}/><pre data-testid="applied-filters">{JSON.stringify(filters)}</pre></main>}
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/hrms/helpdesk'+location.search]}><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}>{new URLSearchParams(location.search).has('native')?<HelpdeskPage/>:<Demo/>}</QueryClientProvider></MemoryRouter>);
