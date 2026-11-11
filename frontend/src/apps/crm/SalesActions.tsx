import { useLocation, useNavigate } from "react-router-dom";
import { useRecordDraft } from "@/hooks/use-record-autosave";
import { announceCreated } from "@/shared/creation/CreationOutcome";
import { useSmartCreation } from "@/shared/creation/SmartCreationProvider";
import CrmRecordFields, { useCrmFieldForm } from "@/shared/custom-fields/CrmRecordFields";
import { CompanyQuickCreate } from "@/shared/master-data/CompanySelect";
import { NativeSelect } from "@/components/ui/native-select";
import { useMobile } from "@/components/mobile/useMobile";
import CompactForm from "@/components/forms/CompactForm";
import {lazy,Suspense,useEffect,useState,useRef} from "react";
import {api} from "@/services/api";
import {Dialog,DialogContent,DialogTitle} from "@/components/ui/dialog";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {PhoneInput} from "@/lib/validation/PhoneInput";
import {useAuthStore} from "@/store/authStore";
import {Bootstrap,errorMessage,leadsApi} from "./leads/api";
import {CaptureDialog} from "./leads/LeadManagementPage";
import {crmApi} from "./api";
import type {SalesRecord} from "./CRMSalesHome";
const QuickDealDialog=lazy(()=>import("./CRMWorkspacePage").then(m=>({default:m.QuickDealDialog})));
const TaskQuickCreate=lazy(()=>import("./TaskQuickCreate"));
const ContactQuickCreate=lazy(()=>import("./CRMWorkspacePage").then(module=>({default:module.CRMContactQuickCreate})));
const base="/crm/productivity";

export function CRMInteractionDialog({record,close,saved,next,activities=[]}:{record:SalesRecord;close:()=>void;saved:()=>void;next?:()=>void;activities?:Record<string,any>[]}){
 const mobile = useMobile();
 const [outcome,setOutcome]=useState("Connected"),[notes,setNotes]=useState(""),[due,setDue]=useState(""),[reason,setReason]=useState(""),[zone,setZone]=useState(record.timezone&&record.timezone!=="Not recorded"?record.timezone:"Asia/Kolkata"),[channel,setChannel]=useState("call");const [busy,setBusy]=useState(false),[error,setError]=useState("");const [complete,setComplete]=useState("");
 const pending=activities.filter(a=>Number(record.entity==="leads"?a.lead_id:a.deal_id)===record.id);
 async function save(openNext=false){setBusy(true);setError("");try{await api.post(`${base}/interaction`,{entity:record.entity,record_id:record.id,channel,outcome,notes,next_follow_up:due?new Date(due).toISOString():null,no_next_reason:reason,timezone:zone,complete_activity_id:complete?Number(complete):null});if(openNext&&next)next();else saved();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}
 return <Dialog open onOpenChange={v=>{if(!v&&!busy)close();}}><DialogContent overlayClassName="z-[110]" className={`z-[111] max-h-[90dvh] overflow-y-auto ${mobile ? "mobile-experience-sheet" : ""}`}><DialogTitle>Log outcome & next step</DialogTitle><p className="text-sm">{record.name} · {record.entity} #{record.id}. Your outcome and next commitment are saved together.</p><fieldset disabled={busy} className="space-y-3"><label className="block text-sm">Interaction<NativeSelect aria-label="Interaction" className="block w-full rounded border p-2" value={channel} onChange={e=>setChannel(e.target.value)}><option value="call">Call</option><option value="meeting">Meeting</option><option value="whatsapp">WhatsApp (record only)</option><option value="email">Email (record only)</option></NativeSelect></label><label className="block text-sm">Outcome<NativeSelect aria-label="Outcome" className="block w-full rounded border p-2" value={outcome} onChange={e=>setOutcome(e.target.value)}>{["Connected","No Answer","Callback Requested","Not Interested"].map(o=><option key={o}>{o}</option>)}</NativeSelect></label><label className="block text-sm">Notes<textarea className="block w-full rounded border p-2" value={notes} onChange={e=>setNotes(e.target.value)} maxLength={4000}/></label><label className="block text-sm">Next follow-up (your local time)<Input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label><label className="block text-sm">Customer time zone<Input list="crm-time-zones" value={zone} onChange={e=>setZone(e.target.value)}/><datalist id="crm-time-zones">{["Asia/Kolkata","Asia/Dubai","Europe/London","America/New_York","America/Los_Angeles","UTC"].map(z=><option key={z}>{z}</option>)}</datalist></label>{due&&<p className="text-xs">Customer local time: {(()=>{try{return new Date(due).toLocaleString(undefined,{timeZone:zone});}catch{return "Choose a valid IANA time zone";}})()}</p>}{!due&&<label className="block text-sm">Reason for no next action<Input value={reason} minLength={3} placeholder="For example: not interested; no further contact requested" onChange={e=>setReason(e.target.value)}/></label>}{!!pending.length&&<label className="block text-sm">Complete pending follow-up<NativeSelect className="block w-full rounded border p-2" value={complete} onChange={e=>setComplete(e.target.value)}><option value="">Log without completing a pending item</option>{pending.map(a=><option key={a.id} value={a.id}>{a.title||a.subject}</option>)}</NativeSelect></label>}<p role="status" className="text-xs text-muted-foreground">Unsaved interaction · entered details stay here if saving fails.</p></fieldset>{error&&<p role="alert" className="text-destructive">{error}</p>}<div className="flex flex-wrap gap-2"><Button disabled={busy||(!due&&reason.trim().length<3)} onClick={()=>void save()}>Save outcome & next step</Button>{next&&<Button variant="outline" disabled={busy||(!due&&reason.trim().length<3)} onClick={()=>void save(true)}>Complete and open next follow-up</Button>}</div></DialogContent></Dialog>;
}

export function CRMHandoverDialog({bootstrap,close,saved}:{bootstrap:Bootstrap;close:()=>void;saved:()=>void}){
 const [from,setFrom]=useState(""),[to,setTo]=useState(""),[reason,setReason]=useState("");const [preview,setPreview]=useState<any>();const [busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
 const change=()=>{setPreview(undefined);setNotice("");};const payload={from_user_id:Number(from),to_user_id:Number(to),reason};
 async function act(apply=false){setBusy(true);setError("");try{const r=await api.post(`${base}/handover/${apply?"apply":"preview"}`,{...payload,...(apply?{preview_version:preview.version}:{})});if(apply){setNotice(r.data.message);setPreview(undefined);saved();}else setPreview(r.data);}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}
 return <Dialog open onOpenChange={v=>{if(!v&&!busy)close();}}><DialogContent className="max-h-[90dvh] max-w-2xl overflow-y-auto"><DialogTitle>Salesperson handover</DialogTitle><p className="text-sm">Transfer open leads, deals, tasks and follow-ups together, within your permitted scope. Archived and closed records remain with their history.</p><fieldset disabled={busy} className="space-y-3"><label className="block text-sm">Departing salesperson<NativeSelect aria-label="Departing salesperson" className="block w-full rounded border p-2" value={from} onChange={e=>{setFrom(e.target.value);change();}}><option value="">Choose user</option>{bootstrap.owners.map(p=><option key={p.id} value={p.id}>{p.name} · {p.email}</option>)}</NativeSelect></label><p className="text-xs">If the departing login is already disabled, enter its user ID from the ownership history.</p><Input type="number" min="1" aria-label="Departing user ID" value={from} onChange={e=>{setFrom(e.target.value);change();}}/><label className="block text-sm">Replacement salesperson<NativeSelect aria-label="Replacement salesperson" className="block w-full rounded border p-2" value={to} onChange={e=>{setTo(e.target.value);change();}}><option value="">Choose eligible user</option>{bootstrap.owners.map(p=><option key={p.id} value={p.id}>{p.name} · {p.email}</option>)}</NativeSelect></label><label className="block text-sm">Reassignment reason<Input value={reason} minLength={3} onChange={e=>{setReason(e.target.value);change();}}/></label></fieldset>{error&&<p role="alert" className="text-destructive">{error}</p>}{notice&&<p role="status">{notice}</p>}<Button disabled={busy||!from||!to||from===to||reason.trim().length<3} onClick={()=>void act()}>Preview affected work & workload</Button>{preview&&<section className="space-y-3 rounded border p-3"><p className="text-sm">Organization #{preview.organization_id} · {preview.scope}</p>{Object.entries(preview.counts).map(([kind,count])=><p className="text-sm" key={kind}>{kind}: {String(count)} to transfer · replacement currently owns {preview.replacement_workload[kind]}</p>)}<details><summary>Review affected records</summary>{Object.entries(preview.items as Record<string,{id:number;name:string}[]>).map(([type,items])=><div key={type}><h3>{type}</h3>{items.map(i=><p className="text-xs" key={i.id}>#{i.id} · {i.name}</p>)}</div>)}</details><Button disabled={busy} onClick={()=>void act(true)}>Apply reviewed handover</Button></section>}</DialogContent></Dialog>;
}

type CRMQuickCreateProps={type:string;close:()=>void;saved:()=>void;direct?:boolean};
export function CRMQuickCreate(props:CRMQuickCreateProps){
 return props.direct || props.type === "reminder" ? <CRMQuickCreateForm {...props}/> : <CRMCreationShortcut {...props}/>;
}
function CRMCreationShortcut({type,close,saved}:CRMQuickCreateProps){
 const creation=useSmartCreation(),navigate=useNavigate(),attempted=useRef(false);
 useEffect(()=>{
  if(attempted.current)return;
  attempted.current=true;
  const resource=({company:"companies",customer:"customers",activity:"activities"} as Record<string,string>)[type]||`${type}s`;
  const destination=type==="task"?"/pms/tasks/new":`/crm/${resource}?new=${resource}`;
  const handled=creation?.open(destination,saved);
  close();
  if(!handled)navigate(destination);
 },[creation,navigate,type,close,saved]);
 return null;
}
function CRMQuickCreateForm({type,close,saved}:CRMQuickCreateProps){
 const location=useLocation(),submitting=useRef(false);
 const customEntity=type==="contact"?"contacts":type==="company"?"companies":["task","reminder"].includes(type)?"tasks":"";
 const customFieldForm=useCrmFieldForm(customEntity,"quick_create");
 const user=useAuthStore(s=>s.user);const [dueAt,setDueAt]=useState("");const [name,setName]=useState("");const [email,setEmail]=useState("");const [phone,setPhone]=useState("");const [code,setCode]=useState("+91");const [bootstrap,setBootstrap]=useState<Bootstrap>();const [error,setError]=useState("");const [busy,setBusy]=useState(false);
 const clearDraft=useRecordDraft(`crm:quick:${type}:${location.pathname}${location.search}`,{name,dueAt},draft=>{setName(draft.name);setDueAt(draft.dueAt);},["reminder","activity"].includes(type));
 const context:Record<string,number>={}; const current=new URLSearchParams(location.search);
 for(const key of ["company_id","contact_id","lead_id","deal_id"]){const value=current.get(key);if(value&&/^\d+$/.test(value))context[key]=Number(value);}
 const currentRecord=location.pathname.match(/^\/crm\/(leads|deals|contacts|companies|customers)\/(\d+)(?:\/360)?$/);if(currentRecord)context[({leads:"lead_id",deals:"deal_id",contacts:"contact_id"} as Record<string,string>)[currentRecord[1]]||"company_id"]=Number(currentRecord[2]);
 const suggestDate=(days:number)=>{const date=new Date();date.setDate(date.getDate()+days);date.setHours(9,0,0,0);setDueAt(`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}T09:00`);};
 useEffect(()=>{if(type==="lead")void leadsApi.bootstrap().then(r=>setBootstrap(r.data)).catch(e=>setError(errorMessage(e)));},[type]);
 if(type==="task")return <Suspense fallback={<p role="status">Loading task form…</p>}><TaskQuickCreate close={close} saved={saved}/></Suspense>;
 if(type==="contact")return <Suspense fallback={<p role="status">Loading contact form…</p>}><ContactQuickCreate close={close} saved={saved}/></Suspense>;
 if(type==="company")return <CompanyQuickCreate recordLabel="company" onClose={close} onSaved={(_,keepOpen)=>{saved();if(!keepOpen)close();}}/>;
 if(type==="customer")return <CompanyQuickCreate roles={["Customer"]} recordLabel="customer" defaultEntityKind="Individual" onClose={close} onSaved={(_,keepOpen)=>{saved();if(!keepOpen)close();}}/>;
 if(type==="deal")return <Suspense fallback={<p role="status">Loading deal form…</p>}><QuickDealDialog placement="create" close={close} saved={saved}/></Suspense>;
 if(type==="lead"&&bootstrap)return <CaptureDialog placement="quick_create" bootstrap={bootstrap} close={close} saved={()=>{saved();close();}}/>;
 async function create(){
  if(submitting.current)return;submitting.current=true;setBusy(true);setError("");
  try{
   if(type==="reminder"){
    if(!dueAt)throw new Error("Choose a reminder date and time");
    if(new Date(dueAt).getTime()<=Date.now())throw new Error("Choose a future reminder time");
    const due=new Date(dueAt).toISOString();
    await crmApi.create("tasks",{...context,customFields:customFieldForm.validate(),title:name.trim(),due_date:due,reminder_at:due,status:"To Do",owner_user_id:user?.id});
    clearDraft();announceCreated({title:"Reminder created",href:"/crm/tasks",status:"To Do"});saved();close();return;
   }
   const entity=type==="activity"?"activities":`${type}s`;
   const payload=type==="activity"?{subject:name.trim(),title:name.trim(),activity_type:"task",owner_user_id:user?.id,status:"Pending"}:{name:name.trim(),owner_user_id:user?.id};
   await crmApi.create(entity,{...context,...payload,...(customEntity?{customFields:customFieldForm.validate()}:{})});clearDraft();saved();close();
  }catch(e){setError(e instanceof Error && !(e as {response?:unknown}).response ? e.message : errorMessage(e));}finally{submitting.current=false;setBusy(false);}
 }
 return <Dialog open onOpenChange={v=>{if(!v&&!busy)close();}}><DialogContent><DialogTitle>Quick Create {type}</DialogTitle>{type==="lead"?<p>Loading lead capture…</p>:<CompactForm className="space-y-3" aria-busy={busy} onSubmit={e=>{e.preventDefault();void create();}}><label className="block text-sm">Title<Input required disabled={busy} value={name} maxLength={180} onChange={e=>setName(e.target.value)}/></label>{type==="reminder"&&<><div className="flex gap-2"><Button type="button" variant="outline" disabled={busy} onClick={()=>suggestDate(1)}>Tomorrow, 9 AM</Button><Button type="button" variant="outline" disabled={busy} onClick={()=>suggestDate(7)}>Next week, 9 AM</Button></div><label className="block text-sm">Remind me at<Input disabled={busy} aria-label="Reminder date and time" type="datetime-local" required value={dueAt} onChange={e=>setDueAt(e.target.value)}/></label><p className="text-xs text-muted-foreground">Times use your device’s local time zone. {Object.keys(context).length?"Linked to the current customer or sales record.":"Personal reminder."}</p></>}{customEntity&&<><CrmRecordFields state={customFieldForm}/>{customFieldForm.loading&&<p role="status">Loading custom fields…</p>}{customFieldForm.error&&<p role="alert">{customFieldForm.error}</p>}</>}<p role="status" className="text-xs text-muted-foreground">{clearDraft.status==="restored"?"Restored your unfinished reminder.":clearDraft.status==="unavailable"?"Draft storage is unavailable. Keep this window open.":"Draft saved for this browser session."}</p><Button disabled={busy||!name.trim()||(type==="reminder"&&!dueAt)||!!customEntity&&(customFieldForm.loading||!!customFieldForm.error)}>{busy?"Saving…":type==="reminder"?"Create reminder":"Create record"}</Button></CompactForm>}{error&&<p role="alert" className="text-destructive">{error}</p>}</DialogContent></Dialog>;
}
