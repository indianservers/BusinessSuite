/** Development-only component fixture; Playwright supplies the synthetic API. */
import React,{useState} from 'react';
import ReactDOM from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import TaskSavedViews,{type TaskView} from '../../src/apps/crm/TaskSavedViews';
import {useAuthStore} from '../../src/store/authStore';
import '../../src/index.css';
if(!import.meta.env.DEV)throw Error('Development fixture only');
useAuthStore.setState({isAuthenticated:true,isHydrated:true,token:'synthetic-browser-fixture',user:{id:7,email:'views-fixture@example.com',role:'Super Admin',is_superuser:true,access:{companyId:1} as any}} as any);
function Demo(){const [scope,setScope]=useState('7:1');const [filters,setFilters]=useState<TaskView>({queue:'overdue',status:'all',priority:'High',mine:true,sort:'due_date:asc',search:'delivery'});
 return <main style={{maxWidth:900,padding:24}}><h1>CRM task view QA</h1><button type="button" onClick={()=>{setScope('7:2');useAuthStore.setState(s=>({user:{...s.user!,access:{...s.user?.access,companyId:2} as any}}))}}>Switch fixture company</button><TaskSavedViews key={scope} scope={scope} filters={filters} onApply={setFilters}/><pre data-testid="applied-filters">{JSON.stringify(filters)}</pre></main>}
ReactDOM.createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/crm/tasks'+location.search]}><Demo/></MemoryRouter>);
