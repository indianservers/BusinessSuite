import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter,useLocation} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {CalendarDays,Boxes} from 'lucide-react';
import AppointmentShell from '@/shared/scheduling/AppointmentShell';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
import '@/shared/scheduling/appointment-mobile.css';
useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:55,email:'crm@example.test',role:'crm_sales_executive',is_superuser:false,access:{managed:true,companyId:1,companyName:'CRM only',organizations:[],memberships:[],isAccessAdmin:false,isGlobalAdmin:false,companyDisabledModules:['srm','hrms'],modules:[{key:'crm',route:'/crm',label:'CRM'},{key:'srm',route:'/srm',label:'Sales'},{key:'hrms',route:'/hrms',label:'HRMS'}],grants:{crm:{enabled:true,role:'crm_sales_executive',scope:'company',permissions:['crm_view'],actions:['view']},srm:{enabled:false,role:'viewer',scope:'company',permissions:[],actions:[]},hrms:{enabled:false,role:'viewer',scope:'company',permissions:[],actions:[]}}}}});
function Content(){const route=useLocation(),[resource,setResource]=useState(false);return route.pathname.includes('appointments')?<AppointmentShell nav={[{label:'Appointments',icon:CalendarDays,active:!resource,onClick:()=>setResource(false)},{label:'Resources',icon:Boxes,active:resource,onClick:()=>setResource(true)}]}><h2>{resource?'Available resources content':'Schedule content'}</h2></AppointmentShell>:<output aria-label="Current route">{route.pathname+route.search+route.hash}</output>}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/crm/appointments']}><Content/></MemoryRouter></QueryClientProvider>);
