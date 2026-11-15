import { readPOSCheckoutIntent } from "@/lib/pos-checkout-intent";
import { financialIntentKey } from "@/lib/financial-intent";
import React, {useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {MemoryRouter} from "react-router-dom";
import {QueryClient,QueryClientProvider,useQuery} from "@tanstack/react-query";
import {useAuthStore} from "@/store/authStore";
import {setPackContext,clearPackContext} from "@/lib/pack-context";
import {recordScope,useRecordScope} from "@/lib/record-scope";
import {syncScope,installRecordSync,startRecordSync,useRecordSync} from "@/shared/record-sync/store";
import {defaultsScope,installFormDefaults,defaultText} from "@/lib/form-defaults";
import {securityAuthStamp} from "@/lib/security-auth-stamp";
import {logicalIntentScope} from "@/lib/logical-intent-scope";
import {installRecordCache} from "@/lib/smart-cache/integration";
import {api} from "@/services/api";
import Billing from "@/apps/srm/industry/ServiceCheckoutBillingPanel";
import POS from "@/apps/srm/pages/SRMPOSPage";
import "@/index.css";
sessionStorage.setItem("suite-tenant","fixture");sessionStorage.setItem("suite-organization","1");sessionStorage.setItem("suite-branch","1");setPackContext("11");
const client=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});
function authority(role:string,revision:number){sessionStorage.setItem("qa-role",role);sessionStorage.setItem("qa-revision",String(revision));useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"x."+btoa(JSON.stringify({sid:"fixture",tenant:"fixture"}))+".x",user:{id:77,employee_id:900,email:"fixture@example.invalid",role:"employee",primary_role:"employee",is_superuser:false,access:{companyId:1,grants:{srm:{enabled:true,permissions:["srm_manage","srm_invoice_create","srm_collection_create"],actions:["view","create"],role:"employee",scope:"company"}},permissions:["srm_manage","srm_invoice_create","srm_collection_create"],modules:[],businessPacks:{state:"ready",contexts:[{contextId:11,branchId:1,branchName:"Branch",packKey:"hospital",packLabel:"Hospital",packVersion:1,role,contextRevision:revision,grantRevision:revision,activationRevision:1}],selectedContextId:11,selectionState:"verified",selectorRequired:false,hasMore:false}}} as never});}
authority(sessionStorage.getItem("qa-role")||"Manager",Number(sessionStorage.getItem("qa-revision")||1));installRecordCache(api,client);installRecordSync(client);
Object.assign(window,{nativeIdentity:()=>{const user=useAuthStore.getState().user!;const {access,...identity}=user;return {identity,access};},authority,nativeEmployee:()=>useAuthStore.getState().user?.employee_id,relinkEmployee:(employee_id:number)=>{const user=useAuthStore.getState().user!;useAuthStore.setState({user:{...user,employee_id}});},loggedOutStamp:()=>securityAuthStamp(null),revokeDiscovery:()=>{clearPackContext();const user=useAuthStore.getState().user!;const access=user.access as any;useAuthStore.setState({user:{...user,access:{...access,businessPacks:{...access.businessPacks,contexts:[],selectedContextId:null,selectionState:"none"}}}});},installPrivateDefault:()=>installFormDefaults({values:{task_priority:"PRIVATE-MANAGER-DEFAULT"},modules:{},companyId:1,branchId:1}),readPrivateDefault:()=>defaultText("task_priority","crm"),legacyIntentProof:()=>{
  const identity=[77,"fixture","1","1","11"];
  const legacy=(role:string,branch="1")=>`business-suite-srm-pos-v2:${encodeURIComponent(JSON.stringify([77,"fixture","1",branch,"11",role,false,{}]))}:uncertain-checkout`;
  const payload={payload:{request_id:"original-uuid",payments:[],lines:[]},sale:{customer:"Private"}};
  const original=JSON.stringify(payload),old=legacy("Manager"),key=financialIntentKey("checkout");
  localStorage.removeItem(key);localStorage.setItem(old,original);localStorage.setItem(legacy("Foreign","9"),JSON.stringify({...payload,payload:{...payload.payload,request_id:"foreign-uuid"}}));
  localStorage.setItem("business-suite-srm-pos-uncertain-checkout",original);
  const first=readPOSCheckoutIntent<typeof payload>(key);authority("Doctor",999);const next=readPOSCheckoutIntent<typeof payload>(key);
  const preserved=localStorage.getItem(old)===original && localStorage.getItem("business-suite-srm-pos-uncertain-checkout")===original;
  localStorage.removeItem(key);localStorage.setItem(legacy("Doctor"),JSON.stringify({...payload,payload:{...payload.payload,request_id:"second-uuid"}}));
  const conflict=readPOSCheckoutIntent<typeof payload>(key);
  return {identity,first:first.payload?.payload.request_id,next:next.payload?.payload.request_id,sourceKeys:next.sourceKeys.includes(old),preserved,conflictLocked:conflict.pending && !conflict.payload,conflictNotAdopted:localStorage.getItem(key)===null};
},implicitSelector:()=>{clearPackContext();const user=useAuthStore.getState().user!;const access=user.access as any;useAuthStore.setState({user:{...user,access:{...access,businessPacks:{...access.businessPacks,selectedContextId:null,selectionState:"none"}}}});},scopes:()=>({record:recordScope(useAuthStore.getState().user),sync:syncScope(),defaults:defaultsScope(),auth:securityAuthStamp(useAuthStore.getState().user),intent:logicalIntentScope()}),relabel:()=>{const user=useAuthStore.getState().user!;const access=user.access as any;useAuthStore.setState({user:{...user,name:"Renamed",access:{...access,companyName:"Renamed",businessPacks:{...access.businessPacks,contexts:access.businessPacks.contexts.map((item:any)=>({...item,branchName:"Renamed branch",packLabel:"Renamed hospital"}))}}}});}});
function Pending(){const entries=useRecordSync();return <><button onClick={()=>void startRecordSync({url:"/fam/invoices/991",method:"put",recordSync:true,data:{title:"PRIVATE-PENDING-FINANCE",amount:100}},async()=>{})}>Save pending finance</button><output aria-label="Pending finance">{entries.map(item=>item.title).join("|")}</output></>;}
function Finance(){const scope=useRecordScope();const query=useQuery({queryKey:["finance-private",scope],queryFn:({signal})=>api.get("/fam/invoices",{signal}).then(result=>result.data),placeholderData:undefined});return <output aria-label="Finance data">{query.data?.secret || (query.isError?"Access unavailable":"Loading")}</output>;}
function BillingFixture(){const [epoch,setEpoch]=useState(0);useEffect(()=>{const remount=()=>setEpoch(value=>value+1);window.addEventListener("qa:remount-billing",remount);return()=>window.removeEventListener("qa:remount-billing",remount);},[]);return <Billing key={epoch} checkoutId={77} serviceCharge="PRIVATE-SOURCE-CHARGE" canCollect onChanged={()=>{}}/>;}
const mode=new URLSearchParams(location.search).get("mode");
if(new URLSearchParams(location.search).get("legacy")==="1") {
  clearPackContext();const user=useAuthStore.getState().user!,access=user.access as any;
  useAuthStore.setState({user:{...user,access:{...access,businessPacks:{state:"ready",contexts:[],hasMore:false,selectorRequired:false,selectedContextId:null,selectionState:"none"}}}});
}
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={["/srm/pos"]}><QueryClientProvider client={client}>{mode==="pos"?<POS/>:mode==="finance"?<><Finance/><Pending/></>:<BillingFixture/>}</QueryClientProvider></MemoryRouter>);
