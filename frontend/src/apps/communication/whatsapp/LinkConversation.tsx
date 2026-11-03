import { useState } from "react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { whatsappBase as base, whatsappError } from "./types";

export default function LinkConversation({ contactId, refresh }: { contactId: number; refresh: () => Promise<void> }) {
  const [entityType,setEntityType]=useState("lead"),[entityId,setEntityId]=useState("");
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState("");
  return <details className="rounded-lg border p-3"><summary className="cursor-pointer text-sm">Assign conversation to a CRM record</summary>
    <p className="my-2 text-xs text-muted-foreground">Use an existing record you can access. Unassigned inbound history will inherit that record’s branch. Other users can access the conversation only through their CRM record permissions.</p>
    <div className="flex flex-wrap gap-2"><select aria-label="Linked CRM record type" className="rounded-md border bg-background px-3" value={entityType} disabled={busy} onChange={e=>setEntityType(e.target.value)}><option value="lead">Lead</option><option value="contact">Contact</option><option value="deal">Deal</option></select>
      <Input className="max-w-40" aria-label="Linked CRM record ID" placeholder="CRM record ID" type="number" min="1" value={entityId} disabled={busy} onChange={e=>setEntityId(e.target.value)} />
      <Button variant="outline" disabled={busy || !Number.isInteger(Number(entityId)) || Number(entityId)<1} onClick={async()=>{
        setBusy(true);setNotice("");
        try { await api.post(base+`/conversations/${contactId}/link`,{entityType,entityId:Number(entityId)});await refresh();setNotice("Conversation linked"); }
        catch(error){setNotice(whatsappError(error));}
        finally{setBusy(false);}
      }}>Link record</Button>
    </div>{notice && <p role="status" className="mt-2 text-sm">{notice}</p>}
  </details>;
}
