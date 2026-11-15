import React from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import LeavePage from '@/apps/hrms/pages/leave/LeavePage';
import SettingsHubPage from '@/pages/SettingsHubPage';
import {useAuthStore} from '@/store/authStore';
import {setPackContext} from '@/lib/pack-context';
import {Toaster} from '@/components/ui/toaster';
import '@/index.css';

function owner(name:'A'|'B',branch=1) {
  const id=name==='A'?1:2;
  sessionStorage.setItem('suite-tenant','fixture-'+name.toLowerCase());
  sessionStorage.setItem('suite-organization',String(id));
  sessionStorage.setItem('suite-branch',String(branch));
  setPackContext(String(id*10+branch));
  const permissions=['employee_view','leave_apply'];
  useAuthStore.setState({isAuthenticated:true,isHydrated:true,
    accessToken:'x.'+btoa(JSON.stringify({sid:'leave-'+id,exp:Math.floor(Date.now()/1000)+3600}))+'.x',
    user:{id,employee_id:id,email:`leave-${name}@example.invalid`,role:'employee',primary_role:'employee',is_superuser:false,is_active:true,
      access:{companyId:id,managed:true,isAccessAdmin:false,isGlobalAdmin:false,permissions,modules:[],
        grants:{hrms:{enabled:true,permissions,actions:['view','create','edit'],scope:'own'}},
        businessPacks:{state:'ready',contexts:[],selectedContextId:null,selectionState:'none',hasMore:false,selectorRequired:false}}} as never});
  window.dispatchEvent(new Event('suite:organization-changed'));
  window.dispatchEvent(new Event('suite:branch-changed'));
}

owner('A');
Object.assign(window,{switchLeaveOwner:owner});
Object.assign(window,{revokeScopeOwner:()=>{const user=useAuthStore.getState().user!;useAuthStore.setState({user:{...user,access:{...user.access!,permissions:[],grants:{hrms:{enabled:true,permissions:[],actions:['view'],scope:'own'}}}} as never});}});
const cache=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});
const settings=new URLSearchParams(location.search).get('mode')==='settings';
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={[settings?'/settings/scope-check':'/hrms/leave']}>{settings?<SettingsHubPage sectionId="scope-check"/>:<LeavePage/>}<Toaster/></MemoryRouter></QueryClientProvider>);
