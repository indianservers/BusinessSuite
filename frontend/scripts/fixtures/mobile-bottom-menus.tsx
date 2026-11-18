import {useState} from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter,useLocation,Routes,Route} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {CalendarDays,Boxes} from 'lucide-react';
import MobileModuleDock from '@/components/layout/MobileModuleDock';
import MobilePortalDock from '@/components/mobile/MobilePortalDock';
import AppointmentShell from '@/shared/scheduling/AppointmentShell';
import AppLayout from '@/components/layout/AppLayout';
import {useAuthStore} from '@/store/authStore';
import {canAccessRoute} from '@/lib/roles';
import '@/index.css';
import '@/shared/scheduling/appointment-mobile.css';
import '@/apps/srm/pages/pos-mobile-reference.css';
const params=new URLSearchParams(location.search),employee=params.has('employee');
useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:55,email:'mobile@example.test',role:employee?'employee':'admin',is_superuser:!employee,employee_id:7}});
(window as any).dockAllowed=(to:string)=>canAccessRoute(to.split('?')[0],useAuthStore.getState().user?.role,useAuthStore.getState().user?.is_superuser);
function Content(){const route=useLocation(),[resource,setResource]=useState(false);if(route.pathname.includes('appointments'))return <AppointmentShell nav={[{label:'Appointments',icon:CalendarDays,active:!resource,onClick:()=>setResource(false)},{label:'Resources',icon:Boxes,active:resource,onClick:()=>setResource(true)}]}><h2>{resource?'Available resources content':'Schedule content'}</h2></AppointmentShell>;
 if(route.pathname==='/srm/pos/terminal')return <div className="pos-booking-workspace"><h1>POS checkout</h1><button type="button" style={{marginTop:'auto'}}>Pay now</button></div>;
 return <main id="suite-main" className="kf-main"><h1>Current module</h1><output aria-label="Current route">{route.pathname+route.search+route.hash}</output><input aria-label="Retained draft" defaultValue="Draft preserved"/></main>;
}
function Fixture(){const route=useLocation();if(params.has('app'))return <Routes><Route element={<AppLayout/>}><Route path="*" element={<Content/>}/></Route></Routes>;
 if(route.pathname.includes('appointments'))return <Content/>;
 if(route.pathname.startsWith('/portal/')){const type=route.pathname.includes('/partner')?'partner':'customer',base='/portal/'+type;return <><Content/><MobilePortalDock type={type} canSubmitLead={params.has('submit')} links={(type==='partner'?['Home','Leads','Commissions','Profile']:['Home','Quotes','Invoices','Projects','Profile']).map((label,i)=>[label,base+(i?'/'+label.toLowerCase():'')])}/></>}
 return <><Content/><MobileModuleDock/></>;
}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[params.get('route')||'/crm/leads']}><Fixture/></MemoryRouter></QueryClientProvider>);
