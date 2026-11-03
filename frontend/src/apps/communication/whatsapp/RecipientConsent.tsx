import { useState } from 'react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ShieldCheck } from 'lucide-react';
import { whatsappBase as base, whatsappError } from './types';
export default function RecipientConsent({to,entityType,entityId,disabled,refresh}:{to:string;entityType?:string;entityId?:number;disabled?:boolean;refresh:()=>Promise<void>}) {
  const [source,setSource]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  async function record(status:string){setBusy(true);setNotice('');try{await api.post(base+'/consent',{to,status,source,...(entityType&&entityId?{entityType,entityId}:{})});setNotice('Consent updated');await refresh();}catch(error){setNotice(whatsappError(error));}finally{setBusy(false);}}
  return <details className="wa-consent-editor"><summary><ShieldCheck size={14}/>Record recipient consent</summary><p>Record permission only when the recipient agreed. Include the form, date, or other evidence. STOP messages opt recipients out automatically.</p><Input aria-label="Consent evidence" placeholder="Consent source or evidence" disabled={disabled||busy} value={source} onChange={e=>setSource(e.target.value)}/><div className="wa-inline-actions"><Button size="sm" variant="outline" disabled={disabled||busy||!to||source.trim().length<3} onClick={()=>void record('opted_in')}>Record opt-in</Button><Button size="sm" variant="outline" disabled={disabled||busy||!to||source.trim().length<3} onClick={()=>void record('opted_out')}>Record opt-out</Button></div>{notice&&<p role="status">{notice}</p>}</details>;
}
