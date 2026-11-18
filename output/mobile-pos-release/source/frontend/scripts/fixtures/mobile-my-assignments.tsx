import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import Page from '@/apps/project-management/pages/MyAssignmentsPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,is_superuser:true,role:'admin'}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/hrms/my-assignments']}><main style={{padding:12}}><Page/></main>{location.search.includes("global") && <nav><a href="/outside-assignments">QA shell destination</a><a href="/new-tab" target="_blank">QA separate tab</a><a href="#details">QA same-page anchor</a></nav>}</MemoryRouter></QueryClientProvider>);
