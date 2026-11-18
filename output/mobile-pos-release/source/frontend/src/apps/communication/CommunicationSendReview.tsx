import { useRef, useState } from 'react';
import { api } from '@/services/api';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { whatsappBase as base, whatsappError, type Message } from './whatsapp/types';
import type { UploadedMedia } from './whatsapp/MessageMedia';
import type { DeliveryResult, PreparedRecipient, SendPayload } from './communication-workspace';

export default function CommunicationSendReview({entries,file,scheduledAt,purpose,scope,onClose,onResult}:{entries:PreparedRecipient[];file?:File;scheduledAt?:string;purpose:'transactional'|'greeting'|'marketing';scope:string;onClose:()=>void;onResult:(result:DeliveryResult)=>void}){
 const [busy,setBusy]=useState(false),[finished,setFinished]=useState(false),[results,setResults]=useState<DeliveryResult[]>([]),[error,setError]=useState('');
 const lock=useRef(false);
 const timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;
 function record(result:DeliveryResult){setResults(previous=>[...previous.filter(r=>r.key!==result.key),result]);onResult(result);}
 async function send(){
  if(lock.current||finished||entries.some(e=>e.reason))return;
  lock.current=true;setBusy(true);setError('');
  try{
   for(const entry of entries){
    let payload:SendPayload={...entry.payload};
    try{
     if(file){
      if(!entry.contact?.id)throw new Error('Open and link this WhatsApp conversation before adding an attachment.');
      const data=new FormData();data.append('file',file);
      const media=(await api.post<UploadedMedia>(`${base}/conversations/${entry.contact.id}/media`,data,{uploadLimitBytes:16*1024*1024})).data;
      payload={...payload,media:media.token};
     }
     // Persist before crossing the sending boundary. Uncertain outcomes are checked, never blindly resent.
     const pending:DeliveryResult={key:payload.requestId,name:entry.name,payload,status:'submitting'};
     try{sessionStorage.setItem(`wa-workspace-pending:${scope}:${payload.requestId}`,JSON.stringify({...pending,scheduledAt,purpose}));}
     catch{throw new Error('Browser storage is unavailable. Enable it so an interrupted send can be reconciled safely.');}
     record(pending);
     if(scheduledAt){
      try{
       const response=(await api.post<{id:number;status:string;dueAt:string}>(base+'/workspace/schedule',{message:payload,scheduledAt,purpose})).data;
       record({...pending,status:response.status,scheduledId:response.id,dueAt:response.dueAt});
       sessionStorage.removeItem(`wa-workspace-pending:${scope}:${payload.requestId}`);
      }catch(error){
       // The scheduling endpoint is idempotent; retain this request for a safe status lookup.
       const status=(error as {response?:{status:number}}).response?.status;
       record({...pending,status:status&&status<500?'rejected':'schedule_unconfirmed',error:whatsappError(error)});
       if(status&&status<500)sessionStorage.removeItem(`wa-workspace-pending:${scope}:${payload.requestId}`);
      }
     }else{
      try{
       const message=(await api.post<Message>(base+'/messages',payload)).data;
       record({...pending,status:message.status,message});
       if(!['submitting','reserved','reconciliation_required'].includes(message.status))sessionStorage.removeItem(`wa-workspace-pending:${scope}:${payload.requestId}`);
      }catch(error){
       try{
        const message=(await api.get<Message>(base+'/messages/by-request/'+payload.requestId)).data;
        record({...pending,status:message.status,message});
        if(!['submitting','reserved','reconciliation_required'].includes(message.status))sessionStorage.removeItem(`wa-workspace-pending:${scope}:${payload.requestId}`);
       }catch{
        const status=(error as {response?:{status:number}}).response?.status;
        const rejected=!!status&&[400,401,403,404,409,413,415,422,429].includes(status);
        record({...pending,status:rejected?'rejected':'reconciliation_required',error:whatsappError(error)});
        if(rejected)sessionStorage.removeItem(`wa-workspace-pending:${scope}:${payload.requestId}`);
       }
      }
     }
    }catch(error){record({key:payload.requestId,name:entry.name,payload,status:'rejected',error:whatsappError(error)});}
   }
   setFinished(true);
  }catch(error){setError(whatsappError(error));}finally{lock.current=false;setBusy(false);}
 }
 return <Dialog open onOpenChange={open=>{if(!open&&!busy)onClose();}}><DialogContent onEscapeKeyDown={event=>{if(busy)event.preventDefault();}} onPointerDownOutside={event=>{if(busy)event.preventDefault();}} className="max-w-3xl max-h-[90vh] overflow-y-auto wac-review"><DialogTitle>Review WhatsApp message{entries.length>1?'s':''}</DialogTitle><DialogDescription>{entries.length} recipient{entries.length===1?'':'s'} · {scheduledAt?`${new Date(scheduledAt).toLocaleString()} (${timezone})`:'Send now'} · {file?`${file.name} (${Math.ceil(file.size/1024)} KB)`:'No attachments'}</DialogDescription>
  <p>Each recipient receives a separate personalized message. Delivery and read receipts update after the provider responds.</p>
  <div className="wac-review-list">{entries.map(entry=><article key={entry.key}><strong>{entry.name}</strong><small>{entry.phone}</small><p>{entry.preview}</p>{entry.reason&&<p role="alert">{entry.reason}</p>}{results.find(r=>r.payload.requestId===entry.payload.requestId)&&<p role="status">{results.find(r=>r.payload.requestId===entry.payload.requestId)?.status.replace(/_/g,' ')} {results.find(r=>r.payload.requestId===entry.payload.requestId)?.error}</p>}</article>)}</div>
  {error&&<p role="alert">{error}</p>}<div className="wac-review-actions"><button disabled={busy} onClick={onClose}>{finished?'Done':'Back to edit'}</button><button disabled={busy||finished||entries.some(e=>e.reason)} onClick={()=>void send()}>{busy?'Processing…':finished?'Review complete':scheduledAt?'Confirm schedule':`Confirm & send to ${entries.length}`}</button></div>
 </DialogContent></Dialog>;
}
