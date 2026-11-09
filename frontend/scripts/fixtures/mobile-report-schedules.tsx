import {useState} from "react";
import {SmartCreateModal} from "../../src/shared/creation/SmartCreateModal";
import MobileExperience from "../../src/components/mobile/MobileExperience";
import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import ReportSchedules from "../../src/apps/hrms/pages/reports/ReportSchedules";
import ReportDeliverySchedule from "../../src/components/reports/ReportDeliverySchedule";
import {Toaster} from "../../src/components/ui/toaster";
import {useAuthStore} from "../../src/store/authStore";
import "../../src/index.css";
useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:'fixture',user:{id:12,email:'owner@example.test',role:'employee',is_superuser:false}});
const shared=new URLSearchParams(location.search).has('shared');
function Embedded(){const[open,setOpen]=useState(true),[value,setValue]=useState('Unrelated draft');return <>{open&&<SmartCreateModal definition={{entity:'project',title:'Outer editor',presentation:'dialog',size:'large'}} onClose={()=>setOpen(false)}><label>Outer draft<input aria-label="Outer draft" value={value} onChange={e=>setValue(e.target.value)}/></label><ReportDeliverySchedule endpoint="/test/mobile-delivery"/></SmartCreateModal>}</>}
createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[shared?'/crm/reports':'/hrms/reports']}><MobileExperience/><main style={{padding:12}}>{new URLSearchParams(location.search).has('embedded')?<Embedded/>:shared?<ReportDeliverySchedule endpoint="/test/mobile-delivery"/>:<ReportSchedules/>}</main><Toaster/></MemoryRouter></QueryClientProvider>);
