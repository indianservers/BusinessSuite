import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { whatsappBase as base,whatsappError,type Message } from "./types";
import { DeliveryEvidence } from "../center/shared";
export default function SentMessages({scope}:{scope:string}){
  const [before,setBefore]=useState<number|undefined>();
  const messages=useQuery({queryKey:['whatsapp',scope,'sent',before],queryFn:async()=>(await api.get<{items:(Message&{contactId:number;recipient:string;name?:string})[];nextBefore:number|null}>(base+'/messages',{params:{before}})).data,refetchInterval:10000});
  return <section className="space-y-4"><h3 className="font-medium">Sent messages & delivery status</h3><p className="text-sm text-muted-foreground">Accepted means Meta accepted the request. Delivered and read come from signed delivery callbacks. An uncertain send is kept for reconciliation and is never automatically resent.</p>
    {messages.isPending&&<p>Loading sent messages…</p>}{messages.isError&&<p role="alert">{whatsappError(messages.error)}</p>}
    {messages.data?.items.map(message=><article className="space-y-2 rounded-xl border p-4" key={message.id}><div className="flex flex-wrap justify-between gap-2"><Link className="font-medium underline" to={`/crm/whatsapp/inbox?conversation=${message.contactId}`}>{message.name||'+'+message.recipient}</Link><span className="rounded-full border px-3 py-1 text-xs">{message.status.replace(/_/g,' ')}</span></div><p className="whitespace-pre-wrap text-sm">{message.body}</p><p className="text-xs text-muted-foreground">Message {message.id} · {new Date(message.createdAt).toLocaleString()}{message.errorCode?' · Meta code '+message.errorCode:''}</p><DeliveryEvidence kind="whatsapp" id={message.id}/></article>)}
    {messages.data&&!messages.data.items.length&&<p className="rounded-xl border p-4 text-sm">No recorded outbound messages in this branch. Older sends made before durable tracking cannot be reconstructed or assumed failed.</p>}
    <div className="flex gap-2">{before&&<Button variant="outline" onClick={()=>setBefore(undefined)}>Latest</Button>}{messages.data?.nextBefore&&<Button variant="outline" onClick={()=>setBefore(messages.data!.nextBefore!)}>Older</Button>}</div>
  </section>;
}
