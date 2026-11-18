import {createRoot} from 'react-dom/client';
import {MemoryRouter,Routes,Route,useLocation,useNavigate} from 'react-router-dom';
import Page from '@/apps/project-management/pages/TransitionApprovalInbox';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,is_superuser:true,role:'admin'}});
createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/pms/transition-approvals']}><Routes><Route path='/pms/transition-approvals' element={<Page/>}/><Route path='/pms/tasks/:id' element={<Destination/>}/></Routes></MemoryRouter>);

function Destination(){const location=useLocation(),navigate=useNavigate();return <main><h1>Task review destination fixture</h1><p>{location.pathname+location.search}</p><button onClick={()=>navigate(-1)}>Back to inbox</button></main>}
Object.assign(window,{__transitionActor:()=>useAuthStore.setState({user:{id:2,is_superuser:true,role:'admin'}})});
