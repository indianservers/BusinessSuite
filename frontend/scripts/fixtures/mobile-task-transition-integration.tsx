import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import TaskWorkspacePage from '@/apps/project-management/pages/TaskWorkspacePage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,is_superuser:true,role:'admin'}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/pms/tasks/91?tab=review']}><TaskWorkspacePage embeddedTaskId={91}/></MemoryRouter></QueryClientProvider>);
