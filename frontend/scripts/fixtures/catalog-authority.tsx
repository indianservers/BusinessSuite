import React from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import CatalogPage from '@/shared/catalog/CatalogPage';
import {useAuthStore} from '@/store/authStore';
import {setPackContext} from '@/lib/pack-context';
import {Toaster} from '@/components/ui/toaster';
import '@/index.css';
sessionStorage.setItem('suite-tenant','catalog-fixture');sessionStorage.setItem('suite-organization','1');if(!location.search.includes('firstBranch=1'))sessionStorage.setItem('suite-branch','1');setPackContext('11');
function authority(role:string,employee_id:number,pack=11){setPackContext(String(pack));const permissions=['srm_view','srm_manage'];useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:77,employee_id,email:'fixture@example.invalid',role:'staff',primary_role:'staff',is_superuser:false,access:{companyId:1,managed:true,isAccessAdmin:false,isGlobalAdmin:false,memberships:[1],modules:[],permissions,grants:{srm:{enabled:true,role:'staff',scope:'org',permissions,actions:['view','create','edit']}},businessPacks:{state:'ready',contexts:[{contextId:pack,branchId:1,branchName:'Branch',packKey:pack===11?'hospital':'restaurant',packLabel:'Pack',packVersion:1,role,contextRevision:1,grantRevision:role==='Manager'?1:2,activationRevision:1}],selectedContextId:pack,selectionState:'verified',hasMore:false,selectorRequired:false}}} as never});}
authority('Manager',900);Object.assign(window,{catalogAuthority:authority,refreshCatalog:()=>window.dispatchEvent(new Event('suite:catalog-changed')),refreshCatalogDefaults:()=>window.dispatchEvent(new Event('suite:form-defaults-changed'))});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={['/srm/products-services']}><CatalogPage source="srm"/><Toaster/></MemoryRouter></QueryClientProvider>);
