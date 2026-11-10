import {useMobileContext} from "@/components/mobile/useMobileContext";
import {syncScope} from "@/shared/record-sync/store";
import {workspaceError} from "./workspaceTypes";
import {useMobile} from "@/components/mobile/useMobile";
import "./clients-mobile.css";
import GroupedRecords from "@/shared/data-grid/GroupedRecords";
import {SharedNumberConfirmation} from "@/shared/master-data/CompanySelect";
import {useEffect,useRef,useState} from "react";
import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import {api} from "@/services/api";
import {useAuthStore} from "@/store/authStore";
import {Button} from "@/components/ui/button";
import {Input} from "@/components/ui/input";
import {Dialog,DialogContent,DialogTitle} from "@/components/ui/dialog";
type Client={id:number;name:string;company_name?:string;email?:string;confirmShared?:boolean;sharedReason?:string};
const endpoint="/project-management/clients";
export default function ClientsPage(){
 const phone=useMobile(480),scope=useMobileContext();
 if(phone&&scope!==syncScope())return <p role="status">Updating client context…</p>;
 return <ClientsContent key={scope}/>;
}
function ClientsContent(){
 const phone=useMobile(480),baseline=useRef(''),saving=useRef(false),deleting=useRef(false);
 const confirmed=useRef<'save'|'delete'|null>(null),verification=useRef<Promise<void>|null>(null);
 const [recovery,setRecovery]=useState<'save'|'delete'|null>(null),[verifying,setVerifying]=useState(false);
 const ownerScope=useRef(syncScope()),mounted=useRef(true);
 useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;};},[]);
 const owns=()=>mounted.current&&ownerScope.current===syncScope();
 const clientKey=phone?["pms-clients",ownerScope.current]:["pms-clients"];
 const openDraft=(value:Client)=>{if(confirmed.current||phone&&!owns())return;baseline.current=JSON.stringify(value);setDraft(value);};
 const closeDraft=()=>{if(phone&&!owns())return;if(save.isPending||saving.current)return;if(phone&&draft&&JSON.stringify(draft)!==baseline.current&&!window.confirm('Discard unsaved client changes?'))return;setDraft(null);};
 const qc=useQueryClient(),user=useAuthStore(s=>s.user),grant=user?.access?.grants?.project_management;
 const permits=(action:string)=>!!user?.is_superuser||!!(grant?.enabled&&grant.permissions.some(p=>["pms_manage_projects","pms_admin"].includes(p))&&grant.actions.includes(action));
 const rows=useQuery({queryKey:clientKey,queryFn:({signal})=>{if(phone&&!owns())throw new Error("Client context changed.");return api.get<Client[]>(endpoint,{recordCache:false,...(phone?{signal}:{})}).then(r=>r.data);}});
 const sourceReady=!recovery&&(!phone||owns()&&rows.isSuccess&&!rows.isFetching&&!rows.isPaused);
 const sourceStatus=(rows.error as {response?:{status?:number}}|null)?.response?.status;
 const withheld=phone&&typeof sourceStatus==='number'&&sourceStatus>=400&&sourceStatus<500;
 const showRows=!phone||owns()&&!!rows.data&&!withheld;
 const waiting=phone&&rows.isPaused;
 const retrySource=()=>{if(phone&&!owns())return;if(rows.isFetching||rows.isPaused||saving.current||deleting.current)return;if(confirmed.current){void verifyConfirmed().catch(()=>undefined);return;}void rows.refetch({cancelRefetch:false});};
 const sourceFeedback=phone&&(rows.isError||waiting||rows.isFetching)&&<div className="pms-clients-source" role={rows.isError?'alert':'status'}>{rows.isError?<><p>Clients could not be loaded. {workspaceError(rows.error)}</p>{rows.data&&!withheld&&<p>Showing last loaded clients. Changes are unavailable until refresh succeeds.</p>}</>:<p>{waiting?(rows.data?'Waiting for a connection. Showing last loaded clients; refresh will resume when connected.':'Clients will load when a connection is available.'):rows.data?'Refreshing clients…':'Loading clients…'}</p>}{rows.isError&&!recovery&&<Button type="button" variant="outline" disabled={rows.isFetching||rows.isPaused||saving.current||deleting.current} onClick={retrySource}>Retry clients</Button>}</div>;
 const [draft,setDraft]=useState<Client|null>(null),[remove,setRemove]=useState<Client|null>(null),[error,setError]=useState("");
 function verifyConfirmed():Promise<void>{
   if(!owns()||!confirmed.current)return Promise.resolve();
   if(verification.current)return verification.current;
   setVerifying(true);
   const request=rows.refetch({cancelRefetch:true,throwOnError:true}).then(result=>{
     if(!owns())return;
     if(!result.isSuccess)throw result.error||new Error('Clients could not be verified.');
     const kind=confirmed.current;confirmed.current=null;setRecovery(null);setError('');
     if(kind==='save')setDraft(null);else if(kind==='delete')setRemove(null);
   }).finally(()=>{verification.current=null;if(owns())setVerifying(false);});
   verification.current=request;return request;
 }
 const recoveryPanel=recovery&&<div className="pms-clients-source"><p role="status">{recovery==='save'?'Client saved. Reload clients to update this view; do not submit again.':'Client deleted. Reload clients to update this view; do not submit again.'}</p><Button type="button" variant="outline" disabled={verifying||rows.isFetching||rows.isPaused} onClick={()=>void verifyConfirmed().catch(()=>undefined)}>Reload saved clients</Button></div>;
 const save=useMutation({mutationFn:async(value:Client)=>{if(phone&&!owns())throw new Error("Client context changed.");const original=rows.data?.find(row=>row.id===value.id);const changes=Object.fromEntries((["name","company_name","email"] as const).filter(key=>value.id?value[key]!==original?.[key]:Boolean(value[key])).map(key=>[key,value[key]]));const payload={...changes,...(value.confirmShared?{confirmShared:true,sharedReason:value.sharedReason||undefined}:{})};return value.id?(await api.patch<Client>(endpoint+"/"+value.id,payload)).data:(await api.post<Client>(endpoint,payload)).data;},onSuccess:async(_data,value)=>{if(phone){if(!owns())return;setError('');confirmed.current='save';setRecovery('save');baseline.current=JSON.stringify(value);void verifyConfirmed().catch(()=>undefined);return;}setDraft(null);await qc.invalidateQueries({queryKey:clientKey,exact:phone});},onError:(error)=>{if(phone&&!owns())return;const detail=(error as {response?:{data?:{detail?:unknown}}}).response?.data?.detail;setError(typeof detail==="string"?detail:detail&&typeof detail==="object"&&"message"in detail?String(detail.message):"Client could not be saved. Check your permission and entered values.");}});
 const destroy=useMutation({mutationFn:(id:number)=>{if(phone&&!owns())throw new Error("Client context changed.");return api.delete(endpoint+"/"+id);},onSuccess:async()=>{if(phone){if(!owns())return;setError('');confirmed.current='delete';setRecovery('delete');void verifyConfirmed().catch(()=>undefined);return;}setRemove(null);await qc.invalidateQueries({queryKey:clientKey,exact:phone});},onError:()=>{if(!phone||owns())setError("Client could not be deleted. Linked or restricted records may need to be retained.");}});
 return <section className="pms-clients space-y-4"><header className="flex justify-between"><h1 className="text-2xl font-semibold">Project clients</h1><Button disabled={!permits("create")||!sourceReady} onClick={()=>{setError("");openDraft({id:0,name:"",company_name:"",email:""});}}>Add client</Button></header>{!draft&&!remove&&recoveryPanel}{phone?(!draft&&!remove&&sourceFeedback):rows.isError&&<p role="alert">Clients could not be loaded. Project management permission is required.</p>}{!phone&&rows.isLoading&&<p>Loading clients…</p>}{phone&&rows.isSuccess&&!rows.data.length&&<p role="status">No clients available.</p>}{showRows&&<div className="divide-y rounded border"><GroupedRecords scope="pms-clients" items={(rows.data) || []} fields={[{id:"company",label:"Company",value:client=>client.company_name || "Individual"}]} gridClassName="space-y-2" renderItem={(row,_index,closePreview)=><article key={row.id} className="pms-client-record flex justify-between p-4"><div><h2>{row.name}</h2><p>{row.company_name} {row.email}</p></div><div className="flex gap-2"><Button disabled={!permits("edit")||!sourceReady} onClick={()=>{setError("");if(phone&&closePreview)closePreview(()=>openDraft({...row}));else openDraft({...row});}} aria-label={phone?`Edit ${row.name}`:undefined}>{phone?"Edit":`Edit ${row.name}`}</Button><Button variant="outline" disabled={!permits("delete")||!sourceReady} onClick={()=>{setError("");if(phone&&closePreview)closePreview(()=>setRemove(row));else setRemove(row);}} aria-label={phone?`Delete ${row.name}`:undefined}>{phone?"Delete":`Delete ${row.name}`}</Button></div></article>}/></div>}
 <Dialog open={!!draft&&(!phone||owns())} onOpenChange={v=>{if(!v)closeDraft();}}><DialogContent className="pms-client-editor"><DialogTitle>{draft?.id?"Edit client":"Add client"}</DialogTitle>{draft&&<form className="space-y-3" onSubmit={e=>{e.preventDefault();if(confirmed.current)return;if(phone&&(saving.current||!sourceReady||!permits(draft.id?"edit":"create")))return;if(phone)saving.current=true;save.mutate(draft,{onSettled:()=>{saving.current=false;}});}}>{recoveryPanel}{phone&&sourceFeedback}{(["name","company_name","email"] as const).map(key=><label className="block" key={key}>{key.replace("_"," ")}<Input aria-label={key.replace("_"," ")} disabled={!!recovery||phone&&save.isPending} required={key==="name"} type={key==="email"?"email":"text"} value={draft[key]||""} onChange={e=>setDraft({...draft,[key]:e.target.value})}/></label>)}{phone||recovery?<fieldset disabled={save.isPending||!!recovery} className="contents"><SharedNumberConfirmation source="project_management" email={draft.email} confirmed={!!draft.confirmShared} reason={draft.sharedReason||""} onChange={(confirmShared,sharedReason)=>setDraft({...draft,confirmShared,sharedReason})}/></fieldset>:<SharedNumberConfirmation source="project_management" email={draft.email} confirmed={!!draft.confirmShared} reason={draft.sharedReason||""} onChange={(confirmShared,sharedReason)=>setDraft({...draft,confirmShared,sharedReason})}/>}{error&&<p role="alert">{error}</p>}{phone?<div className="pms-client-form-actions">{phone&&<Button type="button" variant="outline" disabled={save.isPending} onClick={closeDraft}>Cancel</Button>}<Button type="submit" disabled={save.isPending||!sourceReady||!permits(draft.id?"edit":"create")}>{phone&&save.isPending?"Saving…":"Save client"}</Button></div>:<Button type="submit" disabled={save.isPending||!sourceReady||!permits(draft.id?"edit":"create")}>Save client</Button>}</form>}</DialogContent></Dialog>
 <Dialog open={!!remove&&(!phone||owns())} onOpenChange={v=>{if(!v&&!destroy.isPending)setRemove(null);}}><DialogContent className="pms-client-delete"><DialogTitle>Delete client</DialogTitle>{recoveryPanel}{phone&&sourceFeedback}<p>Delete {remove?.name}?</p>{error&&<p role="alert">{error}</p>}<Button disabled={destroy.isPending||!sourceReady||!permits("delete")} onClick={()=>{if(!remove||confirmed.current||phone&&(deleting.current||!sourceReady||!permits("delete")))return;if(phone)deleting.current=true;destroy.mutate(remove.id,{onSettled:()=>{deleting.current=false;}});}}>Confirm delete</Button></DialogContent></Dialog></section>;
}
