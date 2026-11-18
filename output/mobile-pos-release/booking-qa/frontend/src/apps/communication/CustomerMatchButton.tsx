import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Link2 } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { whatsappBase, whatsappError } from './whatsapp/types';

export default function CustomerMatchButton() {
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const cache=useQueryClient();
  return <div className="flex flex-wrap items-center gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={async()=>{
    setBusy(true);setNotice('');
    try {
      let after=0,recipientAfter=0,matched=0,review=0,unmatched=0;
      do {
        const {data}=await api.post(whatsappBase+'/conversations/match-customers',null,{params:{after,recipient_after:recipientAfter}});
        matched+=data.matched;review+=data.ambiguous+data.conflict;unmatched+=data.unmatched;
        after=data.nextAfter??Number.MAX_SAFE_INTEGER;
        recipientAfter=data.nextRecipientAfter??Number.MAX_SAFE_INTEGER;
      } while(after!==Number.MAX_SAFE_INTEGER||recipientAfter!==Number.MAX_SAFE_INTEGER);
      setNotice(`${matched} linked · ${review} need review · ${unmatched} without a match`);
      await Promise.all([cache.invalidateQueries({queryKey:['whatsapp']}),cache.invalidateQueries({queryKey:['customer-comms']})]);
    } catch(error){setNotice(whatsappError(error));} finally{setBusy(false);}
  }}><Link2 size={14}/>{busy?'Matching customers…':'Match customers'}</Button><span role="status" className="text-xs text-muted-foreground">{notice||'Match phone numbers and emails to existing CRM records in this branch.'}</span></div>;
}
