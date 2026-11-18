import {createRoot} from 'react-dom/client';
import Page from '@/apps/project-management/pages/WorkflowSchemesPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:Number(new URLSearchParams(location.search).get('actor')||1),is_superuser:true,role:'admin'}});
createRoot(document.getElementById('root')!).render(<Page/>);

Object.assign(window,{__workflowActor:()=>useAuthStore.setState({user:{id:9999,is_superuser:true,role:"admin"}})});
