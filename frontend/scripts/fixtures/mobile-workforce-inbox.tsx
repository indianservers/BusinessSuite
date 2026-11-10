import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import Page from '@/apps/project-management/pages/MyNoticesPage';
import {useAuthStore} from '@/store/authStore';
import '@/index.css';
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:1,is_superuser:true,role:'admin'}});
createRoot(document.getElementById('root')!).render(<MemoryRouter initialEntries={['/pms/my-notices']}><main style={{padding:12}}><Page/></main></MemoryRouter>);

Object.assign(window,{__noticeActor:()=>useAuthStore.setState({user:{id:2,is_superuser:true,role:"admin"}})});
