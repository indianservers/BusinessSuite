import PhoneActions from "@/components/PhoneActions";
import { WhatsAppIcon } from "@/components/actions";
import { NativeSelect } from "@/components/ui/native-select";
import { PhoneInput } from "@/lib/validation/PhoneInput";
import { contract } from "@/lib/validation";
import { useEffect,useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Send, Search, Link2, Layers, UserRound, Clock3, ShieldCheck, MessageSquareText, Eye, Info, CheckCheck, Save, RotateCcw, CheckCircle2 } from "lucide-react";
import RecipientConsent from "./RecipientConsent";
import { QuickReplies } from '../center/shared';
import { whatsappBase as base, whatsappError, templateParameters, templateSupported, initials, contactName, type Contact, type Message, type Template } from "./types";

type SendPayload = { requestId: string; to: string; body: string; template?: { name: string; language: { code: string }; components?: unknown[] }; entityType?: string; entityId?: number };
type CRMRecord = { id: number; name?: string; fullName?: string; firstName?: string; lastName?: string; title?: string; phone?: string; phoneCountryCode?: string;email?:string };
export type WhatsAppDraft = { key: string; to: string; body: string; entityType?: "lead" | "contact" | "deal"; entityId?: number };
const recordName=(r:CRMRecord)=>r.fullName || r.name || [r.firstName,r.lastName].filter(Boolean).join(' ') || r.title || `Record ${r.id}`;
export default function Composer({templates,contact,admin,scope,refresh,compact=false,businessName='Your business',initialDraft}:{templates:Template[];contact?:Contact;admin:boolean;scope:string;refresh:()=>Promise<void>;compact?:boolean;businessName?:string;initialDraft?:WhatsAppDraft}) {
  const [to,setTo]=useState(contact?'+'+contact.recipient:initialDraft?.to||''),[body,setBody]=useState(initialDraft?.body||'');
  const [countryCode,setCountryCode]=useState(contract.default_calling_code);
  const callingCode=to.startsWith('+')?([...contract.countries].sort((a,b)=>b.code.length-a.code.length).find(c=>to.startsWith(c.code))?.code||countryCode):countryCode;
  const nationalNumber=to.startsWith(callingCode)?to.slice(callingCode.length):to;
  const [mode,setMode]=useState(contact?.serviceWindowOpen?'text':'template'),[chosen,setChosen]=useState('');
  const [parameters,setParameters]=useState<Record<string,string>>({});
  const [entity,setEntity]=useState(contact?.entityType||initialDraft?.entityType||'lead'),[recordId,setRecordId]=useState(contact?.entityId?String(contact.entityId):initialDraft?.entityId?String(initialDraft.entityId):''),[search,setSearch]=useState('');
  const [busy,setBusy]=useState(false),[notice,setNotice]=useState('');
  const [pending,setPending]=useState<SendPayload|null>(()=>{try{const saved=JSON.parse(sessionStorage.getItem(`whatsapp-draft:${scope}:${contact?.id||initialDraft?.key||'new'}:pending`)||'null');return saved&&typeof saved.requestId==='string'?saved:null;}catch{return null;}}),[result,setResult]=useState<Message|null>(null);
  const draftKey=`whatsapp-draft:${scope}:${contact?.id||initialDraft?.key||'new'}`;
  const [hasDraft,setHasDraft]=useState(()=>!!sessionStorage.getItem(draftKey));
  const [draftReady,setDraftReady]=useState(false),[autosaved,setAutosaved]=useState(''),[lookupTo,setLookupTo]=useState(to);
  useEffect(()=>{const timer=setTimeout(()=>setLookupTo(to),250);return()=>clearTimeout(timer);},[to]);
  const recipientLookup=useQuery({queryKey:['whatsapp',scope,'recipient',lookupTo],enabled:!contact&&/^\+?[1-9]\d{6,14}$/.test(lookupTo),queryFn:async()=>(await api.get<{contact:Contact|null}>(base+'/recipient',{params:{to:lookupTo}})).data.contact});
  const records=useQuery({queryKey:['whatsapp-records',scope,entity,search],enabled:!contact,queryFn:async()=>(await api.get<{items:CRMRecord[]}>(`/crm/${entity==='lead'?'leads':entity==='contact'?'contacts':'deals'}`,{params:{search,per_page:30}})).data.items});
  const recents=useQuery({queryKey:['whatsapp',scope,'recent-contacts'],enabled:!contact,queryFn:async()=>(await api.get<{items:Contact[]}>(base+'/conversations',{params:{limit:12}})).data.items});
  const activeContact=contact||(lookupTo===to?recipientLookup.data:null)||recents.data?.find(c=>c.recipient===to.replace(/[^0-9]/g,''));
  const selectedRecord=records.data?.find(r=>String(r.id)===recordId);
  const approved=templates.filter(t=>t.status==='APPROVED'&&templateSupported(t));
  const template=approved.find(t=>t.name+':'+t.language===chosen);
  const placeholders=templateParameters(template);
  const locked=busy||!!pending||!!result, linked=contact?.entityId||recordId;
  const reasons=[...(!/^\+?[1-9]\d{6,14}$/.test(to)?['Enter a valid international recipient number.']:[]),...(!admin&&!linked?['Choose an accessible CRM record.']:[]),...(activeContact?.consent==='opted_out'?['This recipient has opted out.']:[]),...(mode==='text'&&!activeContact?.serviceWindowOpen?['Text replies require an open 24-hour service window. Use an approved template with opt-in.']:[]),...(mode==='text'&&!body.trim()?['Write a reply.']:[]),...(mode==='template'&&!template?['Choose an approved template.']:[]),...(mode==='template'&&activeContact?.consent!=='opted_in'?['Record recipient opt-in before starting a template conversation.']:[]),...(mode==='template'&&placeholders.some(p=>!parameters[p]?.trim())?['Fill every template field.']:[])];
  const disabled=busy||!!result&&!pending||!pending&&reasons.length>0;
  function recordFields(){return linked?{entityType:contact?.entityType||entity,entityId:Number(linked)}:{};}
  function chooseTemplate(t:Template){setChosen(t.name+':'+t.language);setParameters({});setMode('template');}
  function saveDraft(){sessionStorage.setItem(draftKey,JSON.stringify({to,body,mode,chosen,parameters,entity,recordId}));setHasDraft(true);setNotice('Draft saved in this browser tab.');}
  function restoreDraft(){try{const d=JSON.parse(sessionStorage.getItem(draftKey)||'{}');if(!contact&&typeof d.to==='string')setTo(d.to);if(typeof d.body==='string')setBody(d.body);if(['text','template'].includes(d.mode))setMode(d.mode);if(typeof d.chosen==='string')setChosen(d.chosen);if(d.parameters&&typeof d.parameters==='object')setParameters(Object.fromEntries(Object.entries(d.parameters).filter(([,v])=>typeof v==='string')) as Record<string,string>);if(!contact&&['lead','contact','deal'].includes(d.entity)){setEntity(d.entity);setRecordId(String(d.recordId||''));}setNotice('Saved draft restored. Review the recipient before sending.');}catch{setNotice('This draft could not be restored.');}}
  useEffect(()=>{if(sessionStorage.getItem(draftKey))restoreDraft();setDraftReady(true);},[draftKey]);
  useEffect(()=>{if(!draftReady||locked)return;const timer=setTimeout(()=>{try{if(body||chosen||to&&!contact){sessionStorage.setItem(draftKey,JSON.stringify({to,body,mode,chosen,parameters,entity,recordId}));setHasDraft(true);setAutosaved(new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}));}}catch{setAutosaved('');}},650);return()=>clearTimeout(timer);},[to,body,mode,chosen,parameters,entity,recordId,draftReady,locked,draftKey]);
  const preview=mode==='text'?body:(template?.components?.find(c=>c.type==='BODY')?.text||'').replace(/\{\{\d+\}\}/g,p=>parameters[p]||p);
  async function send() {
    const payload = pending || { requestId: crypto.randomUUID(), to, body: mode === "text" ? body : "", ...recordFields(),
      ...(mode === "template" && template ? { template: { name: template.name, language: { code: template.language },
        ...(placeholders.length ? { components: [{ type: "body", parameters: placeholders.map(p => ({ type: "text", text: parameters[p] })) }] } : {}) } } : {}) };
    sessionStorage.setItem(draftKey+':pending',JSON.stringify(payload));
    setPending(payload); setBusy(true); setNotice("");
    const showOutcome=(message:Message)=>{
      setResult(message);
      const uncertain=["submitting","reconciliation_required","reserved"].includes(message.status);
      setNotice(message.status==='failed'
        ? `Meta reported failure for message ${message.id}${message.errorCode?' (code '+message.errorCode+')':''}. Check Sent & delivery for the recorded result.`
        : uncertain ? `Message ${message.id} is awaiting reconciliation. Its outcome is not confirmed; this is not a confirmed send failure.`
        : `Message ${message.id}: ${message.status.replace(/_/g,' ')}. View Sent & delivery for delivery and read updates.`);
      if(!uncertain){setPending(null);sessionStorage.removeItem(draftKey+':pending');sessionStorage.removeItem(draftKey);setHasDraft(false);}
    };
    try {
      const message = (await api.post<Message>(base + "/messages", payload)).data;
      showOutcome(message);
      await refresh();
    } catch (error) {
      const status = (error as { response?: { status?: number } })?.response?.status;
      // A response/UI failure is not evidence of provider failure. Reconcile the
      // durable request first; this GET never sends another WhatsApp message.
      try {
        showOutcome((await api.get<Message>(base+'/messages/by-request/'+payload.requestId)).data);
        await refresh();
      } catch {
        setNotice(`${whatsappError(error)} ${status===422?'Correct the message fields before sending.':'The send outcome is unconfirmed. Check the original request or Sent & delivery; do not create a duplicate send.'}`);
        if(status===422){setPending(null);sessionStorage.removeItem(draftKey+':pending');}
      }
    } finally { setBusy(false); }
  }
  const editor=<section className={compact?'wa-chat-composer':'wa-compose-card'}>
    {!compact&&<div className="wa-card-heading"><span className="wa-feature-icon"><WhatsAppIcon className="h-6 w-6"/></span><div><h3>Send WhatsApp Message</h3><p>Send an approved template or reply to a customer conversation.</p></div></div>}
    {!contact&&<><div className="wa-record-grid">
      <label className="wa-field"><span><Layers size={14}/>CRM record type</span><NativeSelect className="wa-select" disabled={locked} value={entity} onChange={e=>{setEntity(e.target.value);setRecordId('');}}><option value="lead">Lead</option><option value="contact">Contact</option><option value="deal">Deal</option></NativeSelect></label>
      <label className="wa-field"><span><Search size={14}/>Search CRM <small>(optional)</small></span><Input disabled={locked} placeholder="Name, phone, email or ID…" value={search} onChange={e=>setSearch(e.target.value)}/></label>
      <label className="wa-field"><span><Link2 size={14}/>Link CRM record</span><NativeSelect loading={records.isFetching} error={records.isError} className="wa-select" disabled={locked} value={recordId} onChange={e=>{setRecordId(e.target.value);const r=records.data?.find(r=>String(r.id)===e.target.value);if(r?.phone)setTo(r.phone.startsWith('+')?r.phone:(r.phoneCountryCode||contract.default_calling_code)+r.phone);}}><option value="">{admin?'No CRM record (administrator)':'Choose a record'}</option>{recordId&&!records.data?.some(r=>String(r.id)===recordId)&&<option value={recordId}>Linked {entity} #{recordId}</option>}{records.data?.map(r=><option key={r.id} value={r.id}>{recordName(r)}</option>)}</NativeSelect></label>
    </div>{records.isError&&<p role="alert" className="wa-error">CRM records could not load.</p>}
    <div className="wa-recipient-row"><div className="wa-field wa-phone-field"><span><UserRound size={14}/>Recipient (WhatsApp number)</span><PhoneInput label="Recipient phone" value={nationalNumber} countryCode={callingCode} disabled={locked} onChange={value=>setTo(value?callingCode+value:'')} onCountryCodeChange={code=>{setCountryCode(code);setTo(nationalNumber?code+nationalNumber:'');}}/></div>
      <label className="wa-field wa-recent-picker"><span><Clock3 size={14}/>Recent contacts</span><NativeSelect loading={recents.isFetching} error={recents.isError} aria-label="Recent contacts" className="wa-select" disabled={locked} value="" onChange={e=>{const c=recents.data?.find(c=>String(c.id)===e.target.value);if(c){setTo('+'+c.recipient);setEntity(c.entityType||'lead');setRecordId(c.entityId?String(c.entityId):'');}}}><option value="">Pick a recent conversation</option>{recents.data?.map(c=><option key={c.id} value={c.id}>{contactName(c)}</option>)}</NativeSelect></label>
    </div></>}
    {!compact&&<div className={`wa-consent-strip ${activeContact?.consent==='opted_out'?'is-warning':''}`}><Info size={15}/><span>Consent: {activeContact?.consent.replace(/_/g,' ')||'unknown'}. {activeContact?activeContact.serviceWindowOpen?'24-hour reply window is open.':'Use an approved template with opt-in.':'Record opt-in before starting a template conversation.'}</span></div>}
    <div className="wa-composer-mode-row"><div className="wa-mode-switch" role="group" aria-label="Message type">
      <button type="button" disabled={locked} aria-pressed={mode==='text'} className={mode==='text'?'is-active':''} onClick={()=>setMode('text')}><MessageSquareText size={14}/>Text reply</button>
      <button type="button" disabled={locked} aria-pressed={mode==='template'} className={mode==='template'?'is-active':''} onClick={()=>setMode('template')}><ShieldCheck size={14}/>Approved template</button>
    </div>{compact&&<span className={`wa-window-badge ${contact?.serviceWindowOpen?'is-open':''}`}><Clock3 size={12}/>{contact?.serviceWindowOpen?'24-hour window open':'Reply window closed'}</span>}</div>
    {mode==='template'?<div className="wa-template-fields"><label className="wa-field"><span><Layers size={14}/>Approved template</span><NativeSelect className="wa-select" disabled={locked} value={chosen} onChange={e=>{setChosen(e.target.value);setParameters({});}}><option value="">Choose approved template</option>{approved.map(t=><option key={t.name+t.language} value={t.name+':'+t.language}>{t.name} · {t.language}</option>)}</NativeSelect></label>
      {placeholders.length>0&&<div className="wa-variable-grid">{placeholders.map(p=><div className="wa-field" key={p}><label><span>Template field {p}</span><Input aria-label={`Value for ${p}`} disabled={locked} value={parameters[p]||''} onChange={e=>setParameters({...parameters,[p]:e.target.value})}/></label><NativeSelect aria-label={`Map ${p} to customer field`} className="wa-select" value="" disabled={locked} onChange={e=>{const values:Record<string,string>={name:activeContact?contactName(activeContact):selectedRecord?recordName(selectedRecord):'',phone:to,email:selectedRecord?.email||activeContact?.crmEmail||'',reference:recordId?`${entity} #${recordId}`:''};setParameters({...parameters,[p]:values[e.target.value]||''});}}><option value="">Fill from customer data…</option><option value="name">Customer name</option><option value="phone">WhatsApp number</option><option value="email">Customer email</option><option value="reference">CRM reference</option></NativeSelect></div>)}</div>}
      {compact&&template&&<p className="wa-compact-preview">{preview}</p>}
      {!compact&&<p className="wa-muted-note">Choose a template approved for this business. Fill in each variable before sending.</p>}
    </div>:<label className="wa-message-field"><span className={compact?'sr-only':'wa-field-caption'}>Message</span><textarea aria-label="Message" placeholder={contact?`Type your message to ${contact.name||'this contact'}…`:'Type your message…'} rows={compact?2:5} maxLength={4096} disabled={locked} value={body} onChange={e=>setBody(e.target.value)} onKeyDown={e=>{if(e.key==='/'&&!body){e.preventDefault();e.currentTarget.closest('section')?.querySelector<HTMLElement>('.cc-quick-replies summary')?.click();}if((e.ctrlKey||e.metaKey)&&e.key==='Enter'&&!disabled){e.preventDefault();void send();}}}/><span className="wa-character-count">{body.length}/4096</span></label>}
    {!compact&&<RecipientConsent to={to} entityType={recordFields().entityType} entityId={recordFields().entityId} disabled={locked||!admin&&!linked} refresh={refresh}/>}
    <div className="wa-composer-footer"><div className="wa-inline-actions">{mode==='text'&&<QuickReplies disabled={locked} onInsert={text=>setBody(body?body+'\n\n'+text:text)}/>}<Button size="sm" variant="outline" disabled={locked||!body&&!template} onClick={saveDraft}><Save size={14}/>Save draft</Button>{hasDraft&&<Button size="sm" variant="ghost" disabled={locked} onClick={restoreDraft}><RotateCcw size={13}/>Restore</Button>}{result&&!pending&&<Button size="sm" variant="outline" onClick={()=>{setResult(null);setBody('');setNotice('');}}>New message</Button>}</div>
      <Button className="wa-send-button" disabled={disabled} onClick={()=>void send()}><WhatsAppIcon className="h-4 w-4"/>{busy?'Checking…':pending?'Check original send':compact?'Send reply':'Send message'}</Button>
    </div>
    {autosaved&&!result&&<p className="cc-save-status" role="status">Draft autosaved in this tab · {autosaved}</p>}
    {!pending&&!result&&reasons.length>0&&<details className="wa-muted-note"><summary>Why is sending unavailable?</summary><ul>{reasons.map(reason=><li key={reason}>{reason}</li>)}</ul><p>Your text and template drafts are kept when switching modes.</p></details>}
    {pending&&<p className="wa-outcome-note">Outcome unconfirmed. Checking uses the same request and does not send a duplicate.</p>}
    {notice&&<p role="status" className="wa-outcome-note">{notice}</p>}
  </section>;
  if(compact)return editor;
  return <div className="wa-send-layout"><div className="wa-send-main">{editor}{approved.length>0&&<section className="wa-quick-templates"><div className="wa-small-heading"><Layers size={17}/><h3>Approved templates</h3><span>{approved.length} available</span></div><div>{approved.slice(0,3).map(t=><button key={t.name+t.language} disabled={locked} onClick={()=>chooseTemplate(t)}><span className="wa-template-icon"><Layers size={17}/></span><span><strong>{t.name.replace(/_/g,' ')}</strong><small>{t.language} · {t.category.toLowerCase()}</small></span><b>Use</b></button>)}</div></section>}</div>
    <aside className="wa-send-aside"><section className="wa-preview-card"><div className="wa-small-heading"><Eye size={17}/><h3>{mode==='template'?'Template preview':'Message preview'}</h3>{template&&mode==='template'&&<span className="wa-mini-badge"><ShieldCheck size={12}/>Approved</span>}</div><div className="wa-phone-preview"><div className="wa-phone-notch"/><div className="wa-preview-business">{businessName}<small><PhoneActions value={to} fallback="Select a recipient" /></small></div><div className="wa-preview-message">{preview?<><p>{preview}</p><span>{new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}<CheckCheck size={14}/></span></>:<p className="wa-preview-placeholder">{mode==='template'?'Choose a template to preview your message.':'Your message preview will appear here.'}</p>}</div><p className="wa-preview-caption">Preview only · not sent</p></div></section>
    <section className="wa-recipient-card"><div className="wa-small-heading"><UserRound size={17}/><h3>Selected contact</h3></div><div className="wa-selected-recipient"><span className="wa-avatar">{initials(activeContact?.name||selectedRecord&&recordName(selectedRecord)||'#')}</span><div><strong>{activeContact?.name||selectedRecord&&recordName(selectedRecord)||'New recipient'}</strong><small><PhoneActions value={to} fallback="Choose a contact or enter a number" /></small></div>{linked&&<span className="wa-mini-badge">{entity}</span>}</div></section>
    <section className="wa-guidance"><div className="wa-small-heading"><Info size={17}/><h3>Delivery guidance</h3></div><p><CheckCircle2 size={16}/>Use a template or reply within 24 hours of the last customer message.</p><p><ShieldCheck size={16}/>Record the recipient’s opt-in before initiating template messages.</p><p><CheckCheck size={16}/>Track accepted, delivered, and read updates in Sent & delivery.</p></section>
    </aside></div>;
}
