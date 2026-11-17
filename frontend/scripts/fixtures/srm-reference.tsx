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
import ModuleNavigation from "@/components/layout/ModuleNavigation";
import Appointments from "@/apps/srm/industry/IndustryOperationsPage";
import { ShoppingCart, CalendarDays, Clock3, Users, Receipt, BarChart3, Layers3, MapPin } from "lucide-react";
import POS from "@/apps/srm/pages/SRMPOSPage";
import "@/index.css";
const referencePack = new URLSearchParams(location.search).get("pack") || "general";
sessionStorage.setItem("suite-tenant","fixture");sessionStorage.setItem("suite-organization","1");sessionStorage.setItem("suite-branch","1");setPackContext("11");
const client=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});
function authority(role:string,revision:number){sessionStorage.setItem("qa-role",role);sessionStorage.setItem("qa-revision",String(revision));useAuthStore.setState({isAuthenticated:true,isHydrated:true,accessToken:"x."+btoa(JSON.stringify({sid:"fixture",tenant:"fixture"}))+".x",user:{id:77,employee_id:900,email:"fixture@example.invalid",role:"srm_admin",primary_role:"srm_admin",is_superuser:true,access:{companyId:1,grants:{srm:{enabled:true,permissions:["srm_manage","srm_invoice_create","srm_collection_create"],actions:["view","create"],role:"employee",scope:"company"}},permissions:["srm_manage","srm_invoice_create","srm_collection_create"],modules:[],businessPacks:{state:"ready",contexts:[{contextId:11,branchId:1,branchName:"Branch",packKey:referencePack,packLabel:referencePack,packVersion:1,role,contextRevision:revision,grantRevision:revision,activationRevision:1}],selectedContextId:11,selectionState:"verified",selectorRequired:false,hasMore:false}}} as never});}
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
const surface = new URLSearchParams(location.search).get('surface');
const links = [{to:'/srm/pos/terminal',label:'POS',icon:ShoppingCart},{to:'/srm/appointments',label:'Appointments',icon:CalendarDays},{to:'/srm/scheduled-services',label:'Scheduling',icon:Clock3},{to:'/srm/customers',label:'Customers',icon:Users},{to:'/srm/invoices',label:'Transactions',icon:Receipt},{to:'/srm/reports',label:'Reports',icon:BarChart3}];
createRoot(document.getElementById("root")!).render(<MemoryRouter initialEntries={[surface==='appointments'?'/srm/appointments':'/srm/pos/terminal']}><QueryClientProvider client={client}><div style={{display:'flex',minHeight:'100vh',background:'#faf8ff'}}><aside className="suite-sidebar w-64" style={{width:224,flexShrink:0,background:'linear-gradient(145deg,#340c43,#250039)',color:'white'}}><div style={{display:'flex',gap:12,padding:'24px 18px',alignItems:'center'}}><Layers3 size={38} color="#cd65ff"/><div><strong>Indian Servers</strong><div style={{fontSize:13,marginTop:3}}>{referencePack} Suite</div></div></div><ModuleNavigation modulePath="/srm" customItems={links} onNavigate={()=>{}}/></aside><div style={{minWidth:0,flex:1}}><div style={{height:60,display:'flex',alignItems:'center',justifyContent:'space-between',padding:'0 24px',background:'white',borderBottom:'1px solid #e6d9f5'}}><span style={{display:'flex',gap:8,alignItems:'center',fontSize:13}}><MapPin size={18}/>Branch: Chennai</span><strong style={{fontSize:13}}>Company Admin</strong></div>{surface==='appointments'?<Appointments mode="appointments"/>:<POS/>}</div></div></QueryClientProvider></MemoryRouter>);
