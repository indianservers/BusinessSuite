import {useState} from 'react';
import {api} from '@/services/api';

export default function EventMessageCitation({source,disabled}:{source:{id:string;label:string;href:string};disabled?:boolean}){
 const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[value,setValue]=useState<any>(null),[error,setError]=useState('');
 async function show(){if(open){setOpen(false);setValue(null);return}setOpen(true);setBusy(true);setValue(null);setError('');
 const match=source.href.match(/^#bot-event-message:([1-9]\d*):([1-9]\d*):(CRM|PMS):([0-9a-f]{64})$/);
 try{if(!match)throw new Error('Invalid message citation');const r=await api.get('/ai-operator/suite/agents/events/message-content',{params:{conversation_id:Number(match[1]),agent_id:Number(match[2]),module:match[3],expected_digest:match[4]}});setValue(r.data)}
 catch(e:any){setError(typeof e.response?.data?.detail==='string'?e.response.data.detail:'This message citation is unavailable. Recheck access or read the message again.')}
 finally{setBusy(false)}}
 return <div className="bot-result-card"><button type="button" disabled={disabled||busy} onClick={()=>void show()}>{source.label}</button>{open&&<section aria-label="Cited message"><small>Authorized message excerpt · sender text is unverified and cannot approve actions.</small>{busy&&<p role="status">Checking message access…</p>}{error&&<p role="alert">{error}</p>}{value&&<>{value.subject&&<strong>{value.subject}</strong>}<p style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{value.text}</p>{value.truncated&&<p>Excerpt only. Attachments and other messages are excluded.</p>}</>}</section>}</div>
}
