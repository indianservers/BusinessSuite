import {useState} from "react";
import {platformApi as api} from "@/services/platform-api";
import {Alert, message} from "./shared";

type Preview={company_name:string;company_id:number;workspace:string;confirmation:string;preview_token:string};

export default function CompanyRemoval({ident,onRemoved}:{ident:number;onRemoved:(name:string)=>void}){
 const [preview,setPreview]=useState<Preview>(),[confirmation,setConfirmation]=useState(""),[reason,setReason]=useState("");
 const [ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState("");
 async function inspect(){setBusy(true);setError("");try{const {data}=await api.post<Preview>(`/platform/customers/${ident}/removal/preview`);setPreview(data);setConfirmation("");setAck(false);}catch(e){setError(message(e));}finally{setBusy(false);}}
 async function remove(){if(!preview||busy||!ack||confirmation!==preview.confirmation)return;setBusy(true);setError("");try{
  await api.post(`/platform/customers/${ident}/removal`,{preview_token:preview.preview_token,confirmation,reason});onRemoved(preview.company_name);
 }catch(e){setError(message(e));}finally{setBusy(false);}}
 return <section className="po-panel" aria-label="Remove this company"><h3>Remove company</h3>
  <p>Permanently delete this company’s dedicated workspace, its application records, users and invitations. A minimal removal receipt is retained.</p>
  <Alert error={error}/>
  {!preview?<button disabled={busy} onClick={()=>void inspect()}>{busy?"Checking company…":"Review company removal"}</button>:<form className="po-form" onSubmit={e=>{e.preventDefault();void remove();}}>
   <div className="po-notice"><strong>{preview.company_name}</strong><p>Company #{preview.company_id} · Workspace {preview.workspace}</p><p>This removes every application record in this company’s dedicated database. This cannot be undone.</p></div>
   <label>Removal reason<textarea required minLength={5} maxLength={500} value={reason} onChange={e=>setReason(e.target.value)} disabled={busy}/></label>
   <label>Type {preview.confirmation} to confirm<input required autoComplete="off" value={confirmation} onChange={e=>setConfirmation(e.target.value)} disabled={busy}/></label>
   <label><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} disabled={busy}/>I understand this permanently removes the selected company and its records.</label>
   <div className="po-actions"><button type="button" disabled={busy} onClick={()=>setPreview(undefined)}>Cancel removal</button><button disabled={busy||!ack||confirmation!==preview.confirmation||reason.trim().length<5}>{busy?"Removing company…":"Permanently remove company"}</button></div>
  </form>}
 </section>;
}
