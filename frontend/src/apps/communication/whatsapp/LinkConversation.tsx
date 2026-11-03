import { useState } from "react";
import { useQuery } from '@tanstack/react-query';
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { whatsappBase as base, whatsappError } from "./types";

export default function LinkConversation({ contactId, refresh }: { contactId: number; refresh: () => Promise<void> }) {
  const [entityType,setEntityType]=useState("lead"),[entityId,setEntityId]=useState("");
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState("");
  const matches=useQuery({queryKey:['whatsapp','matches',contactId],queryFn:async()=>(await api.get<{status:string;candidates:{entityType:string;entityId:number;name:string;matchedBy:string}[]}>(base+`/conversations/${contactId}/matches`)).data});
  async function link(kind:string,id:number){
    setBusy(true);setNotice('');
    try {await api.post(base+`/conversations/${contactId}/link`,{entityType:kind,entityId:id});await refresh();await matches.refetch();setNotice('Conversation linked');}
    catch(error){setNotice(whatsappError(error));}finally{setBusy(false);}
  }
  return <details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm">Assign conversation to a CRM record</summary>
    {matches.data&&matches.data.status!=='linked'&&<div className="my-2 space-y-2 text-xs"><p>{matches.data.status==='matched'?'Matching customer found':matches.data.status==='ambiguous'?'Multiple CRM records share this number. Choose the correct record.':'No exact customer match in this branch.'}</p>{matches.data.candidates.map(record=><Button key={`${record.entityType}:${record.entityId}`} variant="outline" size="sm" disabled={busy} onClick={()=>void link(record.entityType,record.entityId)}>{record.name} · {record.entityType} #{record.entityId}</Button>)}</div>}
    <p className="my-2 text-xs text-muted-foreground">Use an existing record you can access. Unassigned inbound history will inherit that record’s branch. Other users can access the conversation only through their CRM record permissions.</p>
    <div className="flex flex-wrap gap-2"><select aria-label="Linked CRM record type" className="rounded-md border bg-background px-3" value={entityType} disabled={busy} onChange={e=>setEntityType(e.target.value)}><option value="lead">Lead</option><option value="contact">Contact</option><option value="deal">Deal</option></select>
      <Input className="max-w-40" aria-label="Linked CRM record ID" placeholder="CRM record ID" type="number" min="1" value={entityId} disabled={busy} onChange={e=>setEntityId(e.target.value)} />
      <Button variant="outline" disabled={busy || !Number.isInteger(Number(entityId)) || Number(entityId)<1} onClick={()=>void link(entityType,Number(entityId))}>Link record</Button>
    </div>{notice && <p role="status" className="mt-2 text-sm">{notice}</p>}
  </details>;
}
