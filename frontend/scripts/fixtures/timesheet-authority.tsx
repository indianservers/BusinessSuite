import React from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import TimesheetsPage from "@/apps/hrms/pages/timesheets/TimesheetsPage";
import {useAuthStore} from "@/store/authStore";
import {setPackContext} from "@/lib/pack-context";
import {Toaster} from "@/components/ui/toaster";
import "@/index.css";
sessionStorage.setItem("suite-tenant","fixture");sessionStorage.setItem("suite-organization","1");sessionStorage.setItem("suite-branch","1");setPackContext("11");
const client=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});
function authority(scope:string,employee_id:number){const permissions=["timesheet_view","timesheet_manage","timesheet_approve","employee_view"];useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"fixture",user:{id:77,employee_id,email:"fixture@example.invalid",role:"hr",primary_role:"hr",is_superuser:false,access:{companyId:1,managed:true,isAccessAdmin:false,isGlobalAdmin:false,memberships:[1],modules:[],permissions,grants:{hrms:{enabled:true,role:"hr",scope,permissions,actions:["view","create","edit","approve"]}},businessPacks:{state:"ready",contexts:[{contextId:11,branchId:1,branchName:"Branch",packKey:"hospital",packLabel:"Hospital",packVersion:1,role:"Manager",contextRevision:1,grantRevision:1,activationRevision:1}],selectedContextId:11,selectionState:"verified",hasMore:false,selectorRequired:false}}} as never});}
authority("organization",900);Object.assign(window,{timesheetAuthority:authority,refreshTimesheets:()=>Promise.all([client.invalidateQueries({queryKey:["timesheets"]}),client.invalidateQueries({queryKey:["timesheet-projects"]})]),refreshTimesheetDefaults:()=>window.dispatchEvent(new Event("suite:form-defaults-changed"))});
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/hrms/timesheets"]}><TimesheetsPage/><Toaster/></MemoryRouter></QueryClientProvider>);
