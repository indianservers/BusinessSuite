import {createRoot} from 'react-dom/client';
import {BrowserRouter,MemoryRouter,Routes,Route,useLocation,useNavigate} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import SuiteNotificationsPage from '@/pages/SuiteNotificationsPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
import '@/components/suite/suite.css';
const restricted=location.search.includes('restricted');
useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:55,email:'phone@example.test',role:restricted?'member':'admin',is_superuser:!restricted,access:{managed:true,companyId:1,companyName:'Mobile company',organizations:[{id:1,name:'Mobile company'}],memberships:[1],isAccessAdmin:!restricted,isGlobalAdmin:!restricted,companyDisabledModules:restricted?['crm']:[],modules:[{key:'pms',route:'/pms',label:'Projects'},{key:'crm',route:'/crm',label:'CRM'}],grants:{pms:{enabled:true,role:'member',scope:'company',permissions:['pms_tasks_view'],actions:[]},crm:{enabled:!restricted,role:'member',scope:'company',permissions:[],actions:[]}}}}});
const historyMode=location.search.includes('history');
function Destination(){const navigate=useNavigate();return <main><h1>Notification destination</h1><button onClick={()=>navigate(-1)}>Return to notifications</button></main>}
function App(){const route=useLocation(),navigate=useNavigate();return <><output aria-label="Current route">{route.pathname+route.search}</output>{historyMode?<><button onClick={()=>navigate(-1)}>History back</button><button onClick={()=>navigate(1)}>History forward</button><Routes><Route path="/notifications" element={<SuiteNotificationsPage/>}/><Route path="*" element={<Destination/>}/></Routes></>:<SuiteNotificationsPage/>}</>}

createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}>{historyMode?<BrowserRouter><App/></BrowserRouter>:<MemoryRouter initialEntries={['/notifications']}><App/></MemoryRouter>}</QueryClientProvider>);
