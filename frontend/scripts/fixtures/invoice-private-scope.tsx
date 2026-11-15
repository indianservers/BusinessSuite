import React from 'react';
import {createRoot} from 'react-dom/client';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import SharedInvoicePage from '@/apps/srm/pages/SharedInvoicePage';
import {useAuthStore} from '@/store/authStore';
import {setPackContext} from '@/lib/pack-context';
import '@/index.css';

function owner(company:'A'|'B', branch=1) {
  const id=company==='A'?1:2;
  sessionStorage.setItem('suite-tenant','invoice-'+company);
  sessionStorage.setItem('suite-organization',String(id));
  sessionStorage.setItem('suite-branch',String(branch));
  setPackContext(String(id*10+branch));
  const permissions=['srm_invoice_view','srm_collection_view','srm_collection_create'];
  useAuthStore.setState({isAuthenticated:true,isHydrated:true,
    accessToken:'x.'+btoa(JSON.stringify({sid:'invoice-'+id,exp:Math.floor(Date.now()/1000)+3600}))+'.x',
    user:{id:7,email:'invoice-scope@example.invalid',role:'employee',primary_role:'employee',is_superuser:false,is_active:true,
      access:{companyId:id,managed:true,isAccessAdmin:false,isGlobalAdmin:false,permissions,
        modules:[{key:'srm',route:'/srm'}],grants:{srm:{enabled:true,permissions,actions:['view','create'],scope:'organization'}},
        businessPacks:{state:'ready',contexts:[],hasMore:false,selectorRequired:false,selectionState:'none',selectedContextId:null}}} as never});
  window.dispatchEvent(new Event('suite:organization-changed'));
  window.dispatchEvent(new Event('suite:branch-changed'));
}
owner('A');
Object.assign(window,{switchInvoiceOwner:owner});
const cache=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={cache}><MemoryRouter initialEntries={['/srm/invoices/3']}><main className="mx-auto max-w-6xl p-4"><Routes><Route path="/srm/invoices/:id" element={<SharedInvoicePage/>}/></Routes></main></MemoryRouter></QueryClientProvider>);
