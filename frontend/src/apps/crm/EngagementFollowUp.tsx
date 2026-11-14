import { Button } from "@/components/ui/button";
import { useRef, useState } from 'react';
import { api } from '@/services/api';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { useRecordScopeOwner } from '@/hooks/use-record-scope-owner';

export default function EngagementFollowUp({kind, identity, title, onClose, onSaved}: {kind:'meetings'|'calls';identity:number;title:string;onClose:()=>void;onSaved:()=>void}) {
  const ownsScope=useRecordScopeOwner();
  const [name,setName]=useState(`Follow up: ${title}`.slice(0,220));
  const [due,setDue]=useState(''),[error,setError]=useState(''),[saving,setSaving]=useState(false);
  const busy=useRef(false);
  async function save(event:React.FormEvent) {
    event.preventDefault();if(busy.current||!ownsScope())return;
    busy.current=true;setSaving(true);setError('');
    try {await api.post(`/crm/engagements/${kind}/${identity}/follow-up`,{title:name.trim(),due:new Date(due).toISOString()});if(ownsScope())onSaved();}
    catch(e){if(ownsScope()){const detail=(e as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;setError(typeof detail==='string'?detail:'Could not save the follow-up. Your entries are retained; please retry.');}}
    finally{busy.current=false;setSaving(false);}
  }
  return <Dialog open onOpenChange={open=>{if(!open&&!saving)onClose();}}><DialogContent><DialogTitle>Create a follow-up task</DialogTitle><DialogDescription>Keep the next commitment with this conversation. The task is assigned to you and retains its linked CRM records.</DialogDescription><form onSubmit={e=>void save(e)} className="space-y-4"><label className="block text-sm">Follow-up title<input className="mt-1 w-full rounded border bg-background p-2" required disabled={saving} maxLength={220} value={name} onChange={e=>setName(e.target.value)}/></label><label className="block text-sm">Follow-up due<input className="mt-1 w-full rounded border bg-background p-2" required disabled={saving} type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/></label><p className="text-xs text-muted-foreground">Time zone: {Intl.DateTimeFormat().resolvedOptions().timeZone}. You can manage the saved task in Tasks.</p>{error&&<p role="alert" className="text-sm text-destructive">{error}</p>}<div className="flex justify-end gap-3"><Button variant="outline" type="button" disabled={saving} onClick={onClose}>Cancel</Button><button type="submit" disabled={saving} className="rounded bg-primary px-4 py-2 text-primary-foreground">{saving?'Saving…':'Save follow-up'}</button></div></form></DialogContent></Dialog>;
}
