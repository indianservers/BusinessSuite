import {createRoot} from 'react-dom/client';
import {BrowserRouter,Route,Routes} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import SuiteNotificationsPage from '@/pages/SuiteNotificationsPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:1,email:'notifications@example.test',role:'admin',is_superuser:true,access:{managed:false,companyId:1,companyName:'QA company',memberships:[1],organizations:[],modules:[],grants:{}} as any}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><Routes><Route path="/notifications" element={<SuiteNotificationsPage/>}/><Route path="*" element={<h1>Notification destination</h1>}/></Routes></BrowserRouter></QueryClientProvider>);
