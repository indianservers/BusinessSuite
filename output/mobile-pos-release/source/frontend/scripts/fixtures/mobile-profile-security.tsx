import {api} from "@/services/api";
import RecordSyncItems from "@/shared/record-sync/RecordSyncItems";
import {installRecordSync} from "@/shared/record-sync/store";
import{createRoot}from'react-dom/client';import{MemoryRouter,useLocation,useNavigate}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import ProfilePage from '@/apps/hrms/pages/profile/ProfilePage';import{useAuthStore}from'@/store/authStore';import{Toaster}from'@/components/ui/toaster';import '@/index.css';
const viewer=location.search.includes('viewer'),employee=location.search.includes('employee');useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:1,employee_id:viewer?undefined:2,role:viewer||employee?'employee':'hr',is_superuser:false,access:{managed:true,companyId:1,companyName:'QA company',memberships:[1],organizations:[],modules:[],grants:{hrms:{enabled:true,role:'employee',scope:'company',permissions:viewer?['timesheet_view']:employee?['timesheet_view']:['timesheet_view','timesheet_manage','timesheet_approve'],actions:viewer?[]:employee?['create']:['create','edit','delete','approve']}}}}});
function RouteObserver(){const l=useLocation(),navigate=useNavigate();return <><output data-route>{l.pathname+l.search}</output><button onClick={()=>navigate(-1)}>Fixture back</button></>}
const client=new QueryClient({defaultOptions:{queries:{retry:false}}});installRecordSync(client);
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/hrms/profile/security']}><RecordSyncItems floating/><main id="suite-main" tabIndex={-1} style={{padding:12}}><ProfilePage/><RouteObserver/></main><Toaster/></MemoryRouter></QueryClientProvider>);

(globalThis as any).__unlinkEssProfile=()=>useAuthStore.setState({user:{...useAuthStore.getState().user,employee_id:undefined}});

(globalThis as any).__setProfileRole=(role:string)=>useAuthStore.setState({user:{...useAuthStore.getState().user,role}});

(globalThis as any).__setPhotoUserId=(id:number)=>useAuthStore.setState({user:{...useAuthStore.getState().user,id}});

(globalThis as any).__seedSyncFeedback=()=>Promise.allSettled(Array.from({length:10},(_,i)=>api.patch(`/crm/contacts/${100+i}`,{full_name:`CompleteContactName123456789012345678901234567890123456789012345678901234567890-${i}`})));
