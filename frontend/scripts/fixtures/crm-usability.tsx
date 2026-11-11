// Layout acceptance only. All suite API calls stay in this adapter; no business writes.
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AxiosError } from "axios";
import AppLayout from "../../src/components/layout/AppLayout";
import ModuleWorkspaceFrame from "../../src/shared/workspace/ModuleWorkspaceFrame";
import EnterpriseDealsPage from "../../src/apps/crm/deals/EnterpriseDealsPage";
import { api } from "../../src/services/api";
import { useAuthStore } from "../../src/store/authStore";
import { localGridSource } from "../../src/shared/data-grid/local-source";
import { emptyQuery, type GridColumn, type GridQuery } from "../../src/shared/data-grid/types";
import "../../src/index.css";
import "../../src/design-system/premium.css";
import "../../src/shared/data-grid/suite-list-surface.css";
import "../../src/shared/priority/priority.css";

if (!import.meta.env.DEV || !["localhost", "127.0.0.1"].includes(location.hostname)) throw new Error("Local development fixture only");
const user = { id: 98261, email: "usability@example.test", name: "QA Seller", role: "admin", is_superuser: true, access: { companyId: 98261, companyName: "DISPOSABLE CRM FIXTURE", managed: false, modules: [], grants: {}, organizations: [], memberships: [], companyDisabledModules: [], isAccessAdmin: true, isGlobalAdmin: true } };
useAuthStore.setState({ isHydrated: true, isAuthenticated: true, accessToken: "local-fixture", user });
const records = Array.from({length: 8}, (_, i) => ({id:i+1,name:`Fixture opportunity ${i+1}`,company_name:"Fixture company",company_id:1,pipeline_id:1,pipeline_name:"Service sales",stage_id:1,stage_name:"Qualification",owner_user_id:user.id,owner_name:user.name,amount:1000+i,currency:i%2?"USD":"INR",probability:20,status:"Open",priority:"Medium",version:1,expected_close_date:"2026-12-10",next_follow_up_at:null,updated_at:"2026-11-11T10:00:00Z"}));
type Deal = typeof records[number];
const columns:GridColumn<Deal>[] = [
  {id:"name",title:"Deal name"},{id:"stage_id",title:"Stage",type:"category",accessor:r=>r.stage_name},
  {id:"company_id",title:"Company",accessor:r=>r.company_name},{id:"owner_user_id",title:"Owner"},
  {id:"amount",title:"Value",type:"currency"},{id:"currency",title:"Currency"},{id:"updated_at",title:"Updated"},
];
api.defaults.adapter = async config => {
  const method=(config.method||"get").toLowerCase();
  if(!["get","head","options"].includes(method) && !config.readOnlyPreview) throw new AxiosError("Writes are disabled in this disposable fixture", "ERR_BAD_REQUEST",config,undefined,{data:{detail:"Read-only fixture"},status:403,statusText:"Forbidden",headers:{},config});
  const url = new URL(config.url || "/", "http://fixture.invalid");
  const path=url.pathname;
  const params=new URLSearchParams(config.params as Record<string,string>);
  let data:unknown=[];
  if(path.endsWith("/grid/query")) {
    const query=JSON.parse(params.get("state")||"null") as GridQuery|null;
    const base=JSON.parse(params.get("base")||"{}");
    const permitted=records.filter(r=>(!base.pipeline_id||String(r.pipeline_id)===String(base.pipeline_id))&&(!base.owner_id||String(r.owner_user_id)===String(base.owner_id))&&(!base.search||r.name.toLowerCase().includes(String(base.search).toLowerCase())));
    const result=await localGridSource("fixture-deals",permitted,columns,r=>String(r.id)).load(query||emptyQuery());
    data={...result,permissions:{edit:false,export:false,archive:false,assign:false},context:{summary:{counts:{open:result.total,closing_month:0,overdue:0},currencies:[],definitions:{}}}};
  } else if(path.endsWith("/deal-workspace/pipelines")) data={items:[{id:1,name:"Service sales",is_default:true}]};
  else if(path.endsWith("/deal-workspace/pipeline-stages")) data={items:[{id:1,pipeline_id:1,name:"Qualification",probability:20}]};
  else if(path.endsWith("/deal-workspace/assignees")) data={items:[{id:user.id,name:user.name}]};
  else if(path.endsWith("/deal-workspace/teams")) data={items:[]};
  else if(path.endsWith("/access/setup")) data={companyId:user.access.companyId,ready:true,items:[]};
  else if(path.endsWith("/access/settings/defaults/effective")) data={values:{},modules:{}};
  else if(path.endsWith("/branches/context")) data={selected:1,branches:[{id:1,name:"DISPOSABLE FIXTURE",can_write:true}]};
  else if(path.includes("notifications")) data={items:[],unread:0,total:0};
  return {data,status:200,statusText:"OK",headers:{},config};
};
createRoot(document.getElementById("root")!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false},mutations:{retry:false}}})}><MemoryRouter initialEntries={["/crm/deals"]}><Routes><Route element={<AppLayout/>}><Route path="/crm/deals" element={<ModuleWorkspaceFrame module="crm"><EnterpriseDealsPage/></ModuleWorkspaceFrame>}/></Route></Routes></MemoryRouter></QueryClientProvider>);
