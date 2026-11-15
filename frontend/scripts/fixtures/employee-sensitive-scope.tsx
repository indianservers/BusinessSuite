import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import EmployeeDetailPage from "@/apps/hrms/pages/employees/EmployeeDetailPage";
import {useAuthStore} from "@/store/authStore";
import {setPackContext} from "@/lib/pack-context";
import "@/index.css";
sessionStorage.setItem("suite-tenant","fixture");sessionStorage.setItem("suite-organization","1");sessionStorage.setItem("suite-branch","1");setPackContext("11");
const client=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});
function sensitive(enabled:boolean){const permissions=["employee_view","employee_update",...(enabled?["employee_sensitive_view"]:[])];useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:77,employee_id:900,email:"fixture@example.invalid",role:"hr",primary_role:"hr",is_superuser:false,access:{companyId:1,managed:true,isAccessAdmin:false,isGlobalAdmin:false,memberships:[1],modules:[],permissions,grants:{hrms:{enabled:true,role:"hr",scope:"organization",permissions,actions:["view","edit"]}},businessPacks:{state:"ready",contexts:[{contextId:11,branchId:1,branchName:"Branch",packKey:"hospital",packLabel:"Hospital",packVersion:1,role:"Manager",contextRevision:1,grantRevision:1,activationRevision:1}],selectedContextId:11,selectionState:"verified",hasMore:false,selectorRequired:false}}} as never});}
sensitive(true);Object.assign(window,{setEmployeeSensitive:sensitive,refreshEmployee:()=>client.invalidateQueries({queryKey:["employee","42"]}),refreshEmployeeDefaults:()=>window.dispatchEvent(new Event("suite:form-defaults-changed"))});
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/hrms/employees/42?tab=bank&edit=true"]}><EmployeeDetailPage employeeId={42} initialEditing/></MemoryRouter></QueryClientProvider>);
