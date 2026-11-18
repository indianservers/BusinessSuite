import {createRoot} from 'react-dom/client';
import {MemoryRouter,useLocation} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import Page from '@/apps/project-management/pages/TaskTypesPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:Number(new URLSearchParams(location.search).get('actor')||1),is_superuser:true,role:'admin'}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/pms/task-types']}><Probe/><Page/></MemoryRouter></QueryClientProvider>);

function Probe(){const value=useLocation();Object.assign(window,{__typeLocation:value.pathname+value.search});return null;}

Object.assign(window,{__taskTypeActor:()=>useAuthStore.setState({user:{id:9999,is_superuser:true,role:"admin"}})});
