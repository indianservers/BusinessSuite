import {useState} from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter,useLocation,useNavigate} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import MobileModuleDock from "../../src/components/layout/MobileModuleDock";
import {useAuthStore} from "../../src/store/authStore";
import "../../src/index.css";
const restricted=new URLSearchParams(location.search).has('restricted');
useAuthStore.setState({isHydrated:true,isAuthenticated:true,accessToken:'fixture',user:{id:55,email:'mobile@example.test',role:restricted?'member':'admin',is_superuser:!restricted,access:{managed:true,companyId:1,companyName:'Mobile test company',organizations:[{id:1,name:'Mobile test company'}],memberships:[1],isAccessAdmin:!restricted,isGlobalAdmin:!restricted,companyDisabledModules:restricted?['crm']:[],modules:[{key:'fam',route:'/fam',label:'Finance'},{key:'crm',route:'/crm',label:'CRM'}],grants:{fam:{enabled:true,role:'member',scope:'company',permissions:[],actions:[]},crm:{enabled:!restricted,role:'member',scope:'company',permissions:[],actions:[]}}}}});
function App(){const route=useLocation(),navigate=useNavigate(),[draft,setDraft]=useState('Retained draft');return <><main id="suite-main"><h1>Mobile navigation fixture</h1><output aria-label="Current route">{route.pathname}</output><label>Unsaved test field<input aria-label="Unsaved test field" value={draft} onChange={e=>setDraft(e.target.value)}/></label><button onClick={()=>navigate(-1)}>Browser back</button><button onClick={()=>navigate('/settings')}>Open settings route</button></main><MobileModuleDock/></>}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[new URLSearchParams(location.search).get('route')||'/fam/invoices']}><App/></MemoryRouter></QueryClientProvider>);
