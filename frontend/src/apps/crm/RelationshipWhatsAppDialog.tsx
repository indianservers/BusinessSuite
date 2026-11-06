import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { api } from "@/services/api";
import { useRecordScope } from "@/shared/records/Record360Workspace";
import Composer from "@/apps/communication/whatsapp/Composer";
import { whatsappBase, whatsappError, type Status, type Template } from "@/apps/communication/whatsapp/types";
import "@/apps/communication/whatsapp/whatsapp.css";

export default function RelationshipWhatsAppDialog({record,close}:{record:{id:number;name:string;phone?:string;phoneCountryCode?:string};close:()=>void}) {
  const scope=useRecordScope(),qc=useQueryClient();
  const status=useQuery({queryKey:["whatsapp",scope,"status"],queryFn:async()=>(await api.get<Status>(whatsappBase+"/status")).data,retry:false});
  const templates=useQuery({queryKey:["whatsapp",scope,"templates"],enabled:status.data?.configured===true,queryFn:async()=>(await api.get<{items:Template[]}>(whatsappBase+"/templates")).data.items,retry:false});
  const refresh=async()=>{await Promise.all([qc.invalidateQueries({queryKey:["whatsapp",scope]}),qc.invalidateQueries({queryKey:["universal-contacts"]})]);};
  return <Dialog open onOpenChange={open=>{if(!open)close();}}><DialogContent className="max-w-5xl"><DialogTitle>WhatsApp · {record.name}</DialogTitle>
    {status.isPending||status.data?.configured&&templates.isPending?<p role="status">Loading WhatsApp connection and approved templates…</p>:status.isError||templates.isError?<div role="alert"><p>{whatsappError(status.error||templates.error)}</p><Button variant="outline" onClick={()=>{void status.refetch();void templates.refetch();}}>Retry</Button></div>:!status.data?.configured?<p role="alert">Connect your company’s WhatsApp account before sending messages.</p>:<Composer key={record.id} templates={templates.data||[]} admin={status.data.canAdmin} scope={scope} businessName={status.data.connection?.businessName} initialDraft={{key:`relationship-hub:${record.id}`,to:record.phone?.startsWith("+")?record.phone:`${record.phoneCountryCode||""}${record.phone||""}`,body:"",entityType:"contact",entityId:record.id}} refresh={refresh}/>}
  </DialogContent></Dialog>;
}
