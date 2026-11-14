import {useEffect, useState} from "react";
import {useQueryClient} from "@tanstack/react-query";
import {recordCache} from "@/lib/smart-cache/integration";
import {api} from "@/services/api";
import {Button} from "@/components/ui/button";
import {useRecordScope} from "@/shared/records/Record360Workspace";
import {useRecordScopeOwner} from "@/hooks/use-record-scope-owner";
import {Dialog, DialogContent, DialogTitle, DialogDescription} from "@/components/ui/dialog";
import {transferError} from "./transfer";

type Status = {requested:boolean; modules:string[]; batch:null|{id:string;branch_id:number;total:number;counts:Record<string,number>}};

export default function CompanySampleData(){
 const scope=useRecordScope();
 return <ScopedCompanySampleData key={scope}/>;
}
function ScopedCompanySampleData(){
 const ownsScope=useRecordScopeOwner();
 const queries=useQueryClient();
 const [status,setStatus]=useState<Status>(),[mode,setMode]=useState<"import"|"delete">(),[confirmation,setConfirmation]=useState("");
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 useEffect(()=>{const controller=new AbortController();void api.get<{available:boolean}>("/imports/sample-data/availability",{signal:controller.signal}).then(({data})=>data.available&&!controller.signal.aborted&&ownsScope()?api.get<Status>("/imports/sample-data/status",{signal:controller.signal}):undefined).then(response=>{if(!response)return;const {data}=response;if(!controller.signal.aborted&&ownsScope())setStatus(data);}).catch(()=>{});return()=>controller.abort();},[]);
 if(!status)return null;
 async function submit(){if(busy||confirmation!==mode||!ownsScope())return;setBusy(true);setError("");try{
  const {data}=await api.post<Status>(`/imports/sample-data/${mode}`,{confirmation,batch_id:status?.batch?.id});if(!ownsScope())return;setStatus(data);setMode(undefined);setConfirmation("");
  void recordCache?.invalidateCache().catch(()=>{});
  void queries.invalidateQueries({type:"active"});
  window.dispatchEvent(new Event("suite:metrics-changed"));window.dispatchEvent(new Event("crm:records-changed"));
 }catch(e){if(ownsScope())setError(transferError(e));}finally{setBusy(false);}}
 return <section className="rounded-xl border bg-white p-4 my-4" aria-label="Company sample data">
  <h2 className="font-semibold">{status.batch?"Company sample data":"Import sample data?"}</h2>
  <p className="text-sm my-2">{status.batch?`${status.batch.total} fictional records imported in branch ${status.batch.branch_id}.`:
   `Explore 300+ fictional records per approved application: ${status.modules.map(m=>m.replace(/_/g," ")).join(", ")}. Import only when you choose. You can delete the sample pack later.`}</p>
  {status.requested&&!status.batch&&<p className="text-sm my-2">You requested sample data during signup. Your company has now been approved.</p>}
  {status.batch&&<details className="text-sm my-2"><summary>Included records</summary><ul>{Object.entries(status.batch.counts).map(([name,count])=><li key={name}>{name.replace(/_/g," ")}: {count}</li>)}</ul></details>}
  <Button variant="outline" disabled={busy||!status.modules.length} onClick={()=>{setMode(status.batch?"delete":"import");setConfirmation("");setError("");}}>{status.batch?"Delete sample data":"Import sample data"}</Button>
  <Dialog open={!!mode} onOpenChange={open=>{if(!open&&!busy)setMode(undefined);}}><DialogContent>
   <DialogTitle>{mode==="delete"?"Delete sample data":"Import sample data"}</DialogTitle>
   <DialogDescription>{mode==="delete"?"Delete the exact sample pack from the branch where it was imported. Changes or dependent records block deletion. Your other records are preserved.":"Create fictional employees, customers, projects, sales and finance records in your approved applications. No invitations, emails, payments or accounting postings are sent."}</DialogDescription>
   <label>Type <strong>{mode}</strong> to confirm<input className="block w-full border rounded p-2 my-2" value={confirmation} onChange={e=>setConfirmation(e.target.value)} autoComplete="off" disabled={busy}/></label>
   {error&&<p role="alert">{error}</p>}
   <Button disabled={busy||confirmation!==mode} onClick={()=>void submit()}>{busy?"Working…":mode==="delete"?"Delete sample data":"Import sample data"}</Button>
  </DialogContent></Dialog>
 </section>;
}
