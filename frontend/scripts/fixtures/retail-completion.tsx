import React from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter,Routes,Route,useNavigate} from 'react-router-dom';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import RetailWorkspace from '@/apps/srm/components/RetailWorkspace';
import FAMWorkspacePage from '@/apps/fam/FAMWorkspacePage';
import SRMWorkspacePage from '@/apps/srm/pages/SRMWorkspacePage';
import SRMPOSPage from '@/apps/srm/pages/SRMPOSPage';
import {useAuthStore} from '@/store/authStore';
import {api} from '@/services/api';
import {setPackContext} from '@/lib/pack-context';
import '@/index.css';
const qa=window as typeof window&{qaAuth:{token:string;branch:string;context:string;implicit?:boolean};qaNavigate:ReturnType<typeof useNavigate>};
sessionStorage.removeItem('suite-tenant');sessionStorage.setItem('suite-organization','1');sessionStorage.setItem('suite-branch',qa.qaAuth.branch);if(!qa.qaAuth.implicit)setPackContext(qa.qaAuth.context);
useAuthStore.setState({isHydrated:false,isAuthenticated:true,accessToken:qa.qaAuth.token,user:null});
function Harness(){qa.qaNavigate=useNavigate();return <Routes>
 <Route path="srm/inventory/stock-in" element={<FAMWorkspacePage kind="inventoryStockIn"/>}/>
 <Route path="srm/inventory/purchase-receipts" element={<FAMWorkspacePage kind="inventoryPurchaseReceipts"/>}/>
 <Route path="srm/inventory/grn" element={<FAMWorkspacePage kind="inventoryPurchaseOrders"/>}/>
 <Route path="srm/inventory/stock-summary" element={<FAMWorkspacePage kind="inventoryStockSummary"/>}/>
 <Route path="srm/inventory/warehouse-stock" element={<FAMWorkspacePage kind="inventoryWarehouseStock"/>}/>
 <Route path="srm/inventory/reports" element={<FAMWorkspacePage kind="inventoryReports"/>}/>
 <Route path="srm/reports" element={<SRMWorkspacePage kind="reports"/>}/>
 <Route path="legacy-reports-boundary" element={<RetailWorkspace mode="daily" fallback={<p>Native report fallback mounted</p>}/>}/>
 <Route path="srm/pos" element={<SRMPOSPage/>}/>
 </Routes>;}
async function mount(){const [identity,access]=await Promise.all([api.get('/auth/me',{recordCache:false}),api.get('/access/me',{recordCache:false})]);const role=typeof identity.data.role==='string'?identity.data.role:identity.data.role?.name||null;useAuthStore.setState({isHydrated:true,user:{...identity.data,role,primary_role:role,access:access.data}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><BrowserRouter><Harness/></BrowserRouter></QueryClientProvider>);}
void mount();
