import {useState} from "react";
import {useNavigate} from "react-router-dom";
import {Mail,Pencil} from "lucide-react";
import {WhatsAppIcon} from "@/components/actions/BrandIcons";
import {api} from "@/services/api";
import {RecordMessageDraft,RecordQuickActions,type CommunicationRecord} from "@/shared/records/RecordWorkspace";
import {openRecordPreview} from "@/components/RecordQuickPreview";
type Row={id:number;name?:string;full_name?:string;email?:string;phone?:string;phone_country_code?:string;status?:string;is_converted?:boolean};
export default function CRMRowQuickActions({record,entity="leads",canEdit=false,onEdit,loadContact=false}:{record:Row;entity?:string;canEdit?:boolean;onEdit?:()=>void;loadContact?:boolean}){
 const navigate=useNavigate(),[draft,setDraft]=useState<{record:CommunicationRecord;channel:"email"|"whatsapp"}>(),[error,setError]=useState(""),[busy,setBusy]=useState(false);
 const contact={...record,name:record.full_name||record.name||"Record"};
 const message=async(channel:"email"|"whatsapp")=>{setBusy(true);setError("");try{const full=loadContact?(await api.get<Row>(`${entity === "leads" ? "/crm/lead-management/leads" : `/crm/${entity}`}/${record.id}`)).data:record;setDraft({record:{...full,name:full.full_name||full.name||contact.name},channel});}catch{setError("Could not load contact details. Please try again.");}finally{setBusy(false);}};
 const edit=onEdit||(()=>navigate(`/crm/${entity}?lead=${record.id}`));
 return <div onClick={e=>e.stopPropagation()} onDoubleClick={e=>e.stopPropagation()}>{loadContact?<div className="record-quick-actions"><button className="record-quick-action email" title="Compose email" aria-label={`Email ${contact.name}`} disabled={busy} onClick={()=>void message("email")}><Mail size={16}/></button><button className="record-quick-action whatsapp" title="Compose WhatsApp message" aria-label={`WhatsApp ${contact.name}`} disabled={busy} onClick={()=>void message("whatsapp")}><WhatsAppIcon width={16} height={16}/></button>{entity==="leads"&&canEdit&&<button className="record-quick-action" title="Edit record" aria-label={`Edit ${contact.name}`} onClick={edit}><Pencil size={16}/></button>}</div>:<RecordQuickActions record={contact} onView={()=>openRecordPreview(record,`/crm/${entity}`)} onMessage={channel=>void message(channel)} onEdit={canEdit&&!record.is_converted?edit:undefined}/>}{error&&<span role="alert">{error}</span>}{draft&&<RecordMessageDraft {...draft} close={()=>setDraft(undefined)}/>}</div>;
}
