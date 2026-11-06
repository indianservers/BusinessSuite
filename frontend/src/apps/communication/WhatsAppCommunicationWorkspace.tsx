import { Fragment, useEffect, useRef, useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import { Link } from 'react-router-dom';

import { MessageCircle, Users, Search, SlidersHorizontal, CheckCircle2, Layers, CalendarDays, FileText, Send, Paperclip, Phone, RefreshCw, Clock, TrendingUp, Star, X, Save } from 'lucide-react';

import { api } from '@/services/api';

import { useDebounced } from '@/shared/master-data/CompanySelect';

import { usePreference } from './center/shared';

import { initials, whatsappBase as base, whatsappError, templateParameters, templateSupported, type Template, type Status, type Message } from './whatsapp/types';

import CommunicationSendReview from './CommunicationSendReview';

import { digits, recipientName, recipientPhone, ownerName, stageName, money, renderTokens, missingTokens, localDateTime, type Recipient, type DirectoryEntry, type Invoice, type PreparedRecipient, type DeliveryResult } from './communication-workspace';

import './whatsapp-communication.css';



const modes = [['Greetings',MessageCircle],['Payment Reminder',Layers],['Send Invoice',FileText],['Follow-up',CalendarDays],['Quotation',TrendingUp],['Order Update',RefreshCw]] as const;

const drafts:Record<string,string>={

 Greetings:'Dear {{contact_name}},\n\nWarm greetings from our team! Thank you for being a valued part of our business. We wish you a wonderful day!',

 'Payment Reminder':'Dear {{contact_name}},\n\nThis is a gentle reminder that invoice {{invoice_number}} for {{due_amount}} is pending. Please complete the payment by {{due_date}}.\n\nThank you for your business!',

 'Send Invoice':'Dear {{contact_name}},\n\nYour invoice {{invoice_number}} for {{due_amount}} is ready. Please find the invoice attached.\n\nThank you for your business!',

 'Follow-up':'Dear {{contact_name}},\n\nFollowing up on our conversation. Please let us know if {{follow_up_date}} is a convenient time to connect.',

 Quotation:'Dear {{contact_name}},\n\nThank you for your interest. We would love to discuss your quotation and answer any questions. Please let us know a convenient time.',

 'Order Update':'Dear {{contact_name}},\n\nWe have an update on your order. Please contact our team for the latest details. Thank you for choosing us!',

};

const defaultFilters={phoneOnly:false,owner:'',stage:'',lastDays:'',availability:'',overdue:false};

type Filters=typeof defaultFilters;

type SavedFilter={name:string;kind:string;search:string;filters:Filters};

type Review={entries:PreparedRecipient[];file?:File;scheduledAt?:string;purpose:'transactional'|'greeting'|'marketing'};



export default function WhatsAppCommunicationWorkspace({scope,source}:{scope:string;source:'crm'|'srm'}){

 const [kind,setKind]=useState('Customers'),[search,setSearch]=useState(''),[page,setPage]=useState(1),[focus,setFocus]=useState<Recipient>(),[checked,setChecked]=useState<Record<number,Recipient>>({});

 const [showFilters,setShowFilters]=useState(false),[filters,setFilters]=useState(defaultFilters),[savedFilters,setSavedFilters]=usePreference<SavedFilter[]>(`wa-filters:${source}`,[]),[filterName,setFilterName]=useState('');

 const [mode,setMode]=useState('Payment Reminder'),[body,setBody]=useState(drafts['Payment Reminder']),[due,setDue]=useState(''),[followUp,setFollowUp]=useState(''),[occasion,setOccasion]=useState('General greeting');

 const [minimum,setMinimum]=useState(''),[maximum,setMaximum]=useState(''),[invoiceIds,setInvoiceIds]=useState<Record<number,string>>({}),[file,setFile]=useState<File>(),[fileOwnerId,setFileOwnerId]=useState<number>(),[fileBusy,setFileBusy]=useState(false),[notice,setNotice]=useState('');

 const [templateKey,setTemplateKey]=useState('draft'),[parameters,setParameters]=useState<Record<string,string>>({}),[favorites,setFavorites]=usePreference<string[]>('wa-template-favorites',[]),[favoritesOnly,setFavoritesOnly]=useState(false);

 const [delivery,setDelivery]=useState('now'),[scheduleTime,setScheduleTime]=useState(''),[review,setReview]=useState<Review>(),[results,setResults]=useState<DeliveryResult[]>(()=>{try{return JSON.parse(sessionStorage.getItem(`wa-workspace-results:${scope}`)||'[]');}catch{return [];}}),[resultFilter,setResultFilter]=useState('all');

 const fileInput=useRef<HTMLInputElement>(null),editor=useRef<HTMLTextAreaElement>(null);

 useEffect(()=>{try{sessionStorage.setItem(`wa-workspace-results:${scope}`,JSON.stringify(results));}catch{/* Pending sends retain their separate durable request keys. */}},[scope,results]);

 useEffect(()=>{

  try{

   const pending:DeliveryResult[]=[];

   for(let index=0;index<sessionStorage.length;index++){

    const key=sessionStorage.key(index);

    if(!key?.startsWith(`wa-workspace-pending:${scope}:`))continue;

    const saved=JSON.parse(sessionStorage.getItem(key)||'null');

    if(saved?.payload?.requestId&&saved?.payload?.to)pending.push({...saved,status:saved.scheduledAt?'schedule_unconfirmed':'reconciliation_required'});

   }

   if(pending.length)setResults(previous=>[...pending,...previous.filter(r=>!pending.some(p=>p.key===r.key))].slice(0,200));

  }catch{setNotice('Some interrupted requests could not be restored. Check the delivery queue before sending again.');}

 },[scope]);

 const term=useDebounced(search),isInvoice=mode==='Payment Reminder'||mode==='Send Invoice',timezone=Intl.DateTimeFormat().resolvedOptions().timeZone;

 const recipients=useQuery({queryKey:['wa-communication',scope,source,kind,term,page],queryFn:async()=>kind==='Leads'?(await api.get<{items:Recipient[];total:number}>('/crm/leads',{params:{search:term,page,per_page:50}})).data:(await api.get<{items:Recipient[];total:number}>('/master-data/companies',{params:{source,role:kind==='Vendors'?'Vendor':'Customer',search:term,page,per_page:50}})).data});

 const account=useQuery({queryKey:['wa-communication',scope,'status'],queryFn:async()=>(await api.get<Status>(base+'/status')).data});

 const templates=useQuery({queryKey:['wa-communication',scope,'templates'],enabled:!!account.data?.configured,queryFn:async()=>(await api.get<{items:Template[]}>(base+'/templates')).data.items});

 const approved=(templates.data||[]).filter(t=>t.status==='APPROVED'&&templateSupported(t));

 const chosenTemplate=approved.find(t=>`${t.name}:${t.language}`===templateKey),templateFields=templateParameters(chosenTemplate);

 const loaded=recipients.data?.items||[],selected=Object.values(checked);

 const lookupRows=[...new Map([...loaded,...selected,...(focus?[focus]:[])].map(r=>[r.id,r])).values()];

 const entries=lookupRows.filter(r=>!!recipientPhone(r)).map(r=>({to:recipientPhone(r),...(kind==='Leads'?{entityType:'lead',entityId:r.id}:r.primaryContactId?{entityType:'contact',entityId:r.primaryContactId}:{})}));

 const directory=useQuery({queryKey:['wa-communication',scope,source,'directory',kind,entries],enabled:entries.length>0,queryFn:async()=>{

  const items:DirectoryEntry[]=[];

  for(let start=0;start<entries.length;start+=50)items.push(...(await api.post<{items:DirectoryEntry[]}>(base+'/workspace/recipients',{entries:entries.slice(start,start+50)},{progress:false})).data.items);

  return items;

 }});

 const metadata=(r:Recipient)=>directory.data?.find(d=>d.to===digits(recipientPhone(r))&&d.entityId===(kind==='Leads'?r.id:r.primaryContactId));

 const invoicesFor=(r:Recipient)=>metadata(r)?.invoices||[];

 const invoiceOptions=(r:Recipient)=>invoicesFor(r).filter(i=>Number(i.balance??i.amount)>=(Number(minimum)||0)&&(!maximum||Number(i.balance??i.amount)<=Number(maximum)));

 const invoiceFor=(r:Recipient)=>invoiceOptions(r).find(i=>String(i.id)===invoiceIds[r.id]);

 const rows=loaded.filter(r=>{

  const details=metadata(r),last=details?.contact?.lastMessageAt;

  return (!filters.phoneOnly||!!recipientPhone(r))&&(!filters.owner||ownerName(r)===filters.owner)&&(!filters.stage||stageName(r)===filters.stage)&&(!filters.availability||(filters.availability==='ready'?details?.contact?.consent==='opted_in'||details?.contact?.serviceWindowOpen:filters.availability==='window'?details?.contact?.serviceWindowOpen:details?.contact?.consent==='opted_out'))&&(!filters.lastDays||!!last&&Date.now()-new Date(last).getTime()>Number(filters.lastDays)*86400000)&&(!filters.overdue||!!details?.invoices.some(i=>Number(i.balance)>0&&!!i.dueAt&&new Date(i.dueAt).getTime()<Date.now()));

 });

 function setFilter<K extends keyof Filters>(key:K,value:Filters[K]){setFilters(previous=>({...previous,[key]:value}));}

 function changeKind(next:string){setKind(next);setPage(1);setFocus(undefined);setChecked({});setInvoiceIds({});setFile(undefined);}

 function chooseMode(next:string){setMode(next);setBody(drafts[next]);setTemplateKey('draft');}

 function toggle(r:Recipient){setChecked(previous=>{const next={...previous};if(next[r.id])delete next[r.id];else next[r.id]=r;return next;});}

 function valuesFor(r:Recipient){const invoice=invoiceFor(r);return {contact_name:recipientName(r),company_name:r.name||recipientName(r),invoice_number:invoice?.name||'{{invoice_number}}',due_amount:invoice?money(invoice.balance??invoice.amount,invoice.currency):'{{due_amount}}',due_date:due||invoice?.dueAt?.slice(0,10)||'{{due_date}}',follow_up_date:followUp||'{{follow_up_date}}',occasion};}

 function previewFor(r?:Recipient){const values=r?valuesFor(r):{contact_name:'{{contact_name}}'};return chosenTemplate?renderTokens((chosenTemplate.components?.find(c=>c.type==='BODY')?.text||'').replace(/\{\{\d+\}\}/g,token=>parameters[token]||token),values):renderTokens(body,values);}

 const preview=previewFor(focus),missing=missingTokens(preview),focusMetadata=focus?metadata(focus):undefined,invoice=focus?invoiceFor(focus):undefined;

 const focusInvoices=focus?invoiceOptions(focus):[];

 const purpose=chosenTemplate?.category==='MARKETING'?'marketing':mode==='Greetings'?'greeting':'transactional';

 const readyToReview=selected.length>0&&!!account.data?.configured&&!directory.isFetching&&!directory.isError&&!fileBusy&&!(minimum&&maximum&&Number(minimum)>Number(maximum))&&(!delivery||delivery==='now'||!!scheduleTime&&new Date(scheduleTime).getTime()>Date.now())&&(!templateKey||templateKey==='draft'||!!chosenTemplate);

 function addFile(next?:File){if(!next)return;if(!/\.(pdf|jpe?g|png)$/i.test(next.name)){setNotice('Choose a PDF, JPG or PNG file.');return;}if(next.size>16*1024*1024){setNotice('Choose a file smaller than 16 MB.');return;}setFile(next);setFileOwnerId(undefined);setNotice('');return true;}

 async function attachInvoice(){if(!invoice)return;setFileBusy(true);setNotice('');try{const blob=(await api.get<Blob>(`/srm/invoices/${invoice.id}/pdf`,{responseType:'blob'})).data;if(addFile(new File([blob],`${invoice.name}.pdf`,{type:'application/pdf'})))setFileOwnerId(focus?.id);}catch(error){setNotice(whatsappError(error));}finally{setFileBusy(false);}}

 function insertToken(token:string){const position=editor.current?.selectionStart??body.length;setBody(body.slice(0,position)+token+body.slice(position));requestAnimationFrame(()=>{editor.current?.focus();editor.current?.setSelectionRange(position+token.length,position+token.length);});}

 function prepare(r:Recipient):PreparedRecipient{

  const details=metadata(r),phone=recipientPhone(r),text=previewFor(r),entityId=kind==='Leads'?r.id:r.primaryContactId;

  const filled=templateFields.map(field=>renderTokens(parameters[field]||field,valuesFor(r)));

  const payload={requestId:crypto.randomUUID(),to:phone,body:chosenTemplate?'':text,...(entityId?{entityType:kind==='Leads'?'lead' as const:'contact' as const,entityId}:{}),...(chosenTemplate?{template:{name:chosenTemplate.name,language:{code:chosenTemplate.language},...(templateFields.length?{components:[{type:'body',parameters:filled.map(value=>({type:'text',text:value}))}]}:{})}}:{})};

  const reason=visibleResults.some(result=>digits(result.payload.to)===digits(phone)&&['submitting','reserved','reconciliation_required','schedule_unconfirmed'].includes(result.status))?'Check this recipient’s original request before creating another send.':!phone?'Record a valid international mobile number.':/^(blocked|inactive|do not contact)$/i.test(r.status||'')?'This contact is blocked or inactive.':details?.unavailable?'You do not have access to this WhatsApp conversation.':!entityId&&!account.data?.canAdmin?'Link a CRM contact before sending.':details?.contact?.consent==='opted_out'?'This recipient has opted out.':missingTokens(text).length?'Complete these fields: '+missingTokens(text).join(', '):!text.trim()?'Write a message.':chosenTemplate&&details?.contact?.consent!=='opted_in'?'Record WhatsApp opt-in before using an approved template.':!chosenTemplate&&!details?.contact?.serviceWindowOpen?'The reply window is closed. Choose an approved template.':file&&fileOwnerId!==undefined&&fileOwnerId!==r.id?'This invoice attachment belongs to another recipient. Attach the matching document.':file&&chosenTemplate?'Remove the attachment or use an editable reply draft.':file&&!details?.contact?.id?'Link the WhatsApp conversation before attaching a file.':file&&text.length>1024?'Attachment captions must be at most 1,024 characters.':delivery==='schedule'&&!chosenTemplate?'Choose an approved template for scheduled delivery.':mode==='Send Invoice'&&!file&&!chosenTemplate?'Attach the invoice PDF before sending this draft.':undefined;

  return {key:`${kind}:${r.id}`,name:recipientName(r),phone,preview:text,payload,contact:details?.contact,invoice:invoiceFor(r),reason};

 }

 function openReview(){if(!readyToReview)return;const seen=new Set<string>();const prepared=selected.map(r=>{const entry=prepare(r);if(seen.has(digits(entry.phone)))entry.reason='This phone number is already selected. Keep one recipient per number.';seen.add(digits(entry.phone));return entry;});setReview({entries:prepared,file,scheduledAt:delivery==='schedule'?new Date(scheduleTime).toISOString():undefined,purpose});}

 function recordResult(result:DeliveryResult){setResults(previous=>[result,...previous.filter(r=>r.key!==result.key)].slice(0,200));}

 const outcomes=useQuery({queryKey:['wa-communication',scope,'outcomes',results.map(r=>r.key).join(',')],enabled:results.length>0,refetchInterval:15000,queryFn:async()=>{

  const updated:Record<string,Partial<DeliveryResult>>={};

  for(const result of results.slice(0,50)){

   try{

    if(result.scheduledId||result.status==='schedule_unconfirmed'){

     const row=(await api.get<{id:number;status:string;dueAt:string;error?:string;message?:Message}>(base+'/workspace/schedules/'+result.payload.requestId)).data;

     updated[result.key]={status:row.status,scheduledId:row.id,dueAt:row.dueAt,error:row.error,message:row.message};sessionStorage.removeItem(`wa-workspace-pending:${scope}:${result.payload.requestId}`);

    }else if(result.status!=='rejected'){

     const message=(await api.get<Message>(base+'/messages/by-request/'+result.payload.requestId)).data;updated[result.key]={message,status:message.status};if(!['submitting','reserved','reconciliation_required'].includes(message.status))sessionStorage.removeItem(`wa-workspace-pending:${scope}:${result.payload.requestId}`);

    }

   }catch{/* Keep the last confirmed status when polling fails. */}

  }

  return updated;

 }});

 useEffect(()=>{
  if(outcomes.data&&Object.keys(outcomes.data).length)setResults(previous=>previous.map(result=>({...result,...outcomes.data?.[result.key]})));
 },[outcomes.data]);
 const visibleResults=results.map(r=>({...r,...outcomes.data?.[r.key]}));

 const displayedResults=visibleResults.filter(r=>resultFilter==='all'||r.status===resultFilter||resultFilter==='issues'&&['failed','blocked','rejected','reconciliation_required','schedule_unconfirmed'].includes(r.status));

 async function retry(result:DeliveryResult){setNotice('');try{const latest=(await api.get<Message>(base+'/messages/by-request/'+result.payload.requestId)).data;if(latest.status!=='failed'||latest.providerMessageId){setNotice('This outcome must be reconciled before retrying.');void outcomes.refetch();return;}setReview({entries:[{key:result.key,name:result.name,phone:result.payload.to,preview:result.payload.body||'Retry approved template: '+result.payload.template?.name,payload:{...result.payload,requestId:crypto.randomUUID()}}],purpose:'transactional'});}catch(error){setNotice(whatsappError(error));}}

 function tomorrow(){const date=new Date();date.setDate(date.getDate()+1);date.setHours(9,0,0,0);setDelivery('schedule');setScheduleTime(localDateTime(date));}

 const activeFilterCount=Object.values(filters).filter(Boolean).length;

 return <section className="wac-page">

  <header className="wac-heading"><span className="wac-brand"><MessageCircle/></span><div><h1>WhatsApp Communication</h1><p>Send personalized messages, reminders, invoices and greetings</p></div><nav aria-label="Communication module"><Link aria-current={source==='crm'?'page':undefined} to="/crm/whatsapp-communication">CRM</Link><Link aria-current={source==='srm'?'page':undefined} to="/srm/whatsapp-communication">Sales</Link></nav></header>

  <div className="wac-layout"><aside className="wac-sidebar">

   <div className="wac-segment"><button className="active"><MessageCircle size={17}/>Chats</button><Link to="/crm/whatsapp?workspace=campaigns"><Send size={16}/>Broadcasts</Link></div>

   <h2><Users size={19}/>Contacts</h2><div className="wac-types">{['Leads','Vendors','Customers'].map(k=><button key={k} className={kind===k?'active':''} aria-pressed={kind===k} onClick={()=>changeKind(k)}>{k}</button>)}</div>

   <label className="wac-search"><Search size={17}/><input aria-label="Search contacts" placeholder="Search contacts, company, mobile…" value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}/></label>

   <button className="wac-filter" aria-expanded={showFilters} onClick={()=>setShowFilters(!showFilters)}><SlidersHorizontal size={16}/>Contact Filters{activeFilterCount>0&&<b>{activeFilterCount}</b>}<span>{showFilters?'−':'+'}</span></button>

   {showFilters&&<div className="wac-filter-panel"><p>Filters apply to the loaded page of contacts.</p><label className="wac-check"><input type="checkbox" checked={filters.phoneOnly} onChange={e=>setFilter('phoneOnly',e.target.checked)}/>With mobile number</label><label>Owner<select aria-label="Owner" value={filters.owner} onChange={e=>setFilter('owner',e.target.value)}><option value="">All owners</option>{[...new Set(loaded.map(ownerName))].map(owner=><option key={owner}>{owner}</option>)}</select></label><label>Stage / status<select aria-label="Stage / status" value={filters.stage} onChange={e=>setFilter('stage',e.target.value)}><option value="">All stages</option>{[...new Set(loaded.map(stageName))].map(stage=><option key={stage}>{stage}</option>)}</select></label><label>WhatsApp availability<select aria-label="WhatsApp availability" value={filters.availability} onChange={e=>setFilter('availability',e.target.value)}><option value="">All contacts</option><option value="ready">Opted in or reply window open</option><option value="window">Reply window open</option><option value="opted_out">Opted out</option></select></label><label>Last communication<select aria-label="Last communication" value={filters.lastDays} onChange={e=>setFilter('lastDays',e.target.value)}><option value="">Any time</option><option value="7">More than 7 days ago</option><option value="30">More than 30 days ago</option></select></label><label className="wac-check"><input type="checkbox" checked={filters.overdue} onChange={e=>setFilter('overdue',e.target.checked)}/>Has overdue invoice balance</label><button onClick={()=>setFilters(defaultFilters)}>Clear filters</button><div className="wac-save-filter"><input aria-label="Saved filter name" placeholder="Name this filter" value={filterName} maxLength={80} onChange={e=>setFilterName(e.target.value)}/><button disabled={!filterName.trim()} onClick={()=>{setSavedFilters(previous=>[...previous.filter(f=>f.name!==filterName.trim()),{name:filterName.trim(),kind,search,filters}].slice(-20));setFilterName('');}}><Save size={14}/>Save</button></div></div>}

   {savedFilters.length>0&&<div className="wac-saved-filters">{savedFilters.map(f=><span key={f.name}><button onClick={()=>{changeKind(f.kind);setSearch(f.search);setFilters(f.filters);}}>{f.name}</button><button aria-label={`Delete filter ${f.name}`} onClick={()=>setSavedFilters(previous=>previous.filter(item=>item.name!==f.name))}><X size={12}/></button></span>)}</div>}

   <div className="wac-counts"><div><Users/><strong>{recipients.data?.total??'—'}</strong><small>Matches</small></div><div><CheckCircle2/><strong>{selected.length}</strong><small>Selected</small></div><div><Layers/><strong>{rows.length}</strong><small>Visible</small></div></div>

   <div className="wac-select-all"><label><input type="checkbox" aria-label="Select all filtered contacts on this page" checked={rows.length>0&&rows.every(r=>!!checked[r.id])} onChange={e=>setChecked(previous=>{const next={...previous};for(const r of rows){if(e.target.checked)next[r.id]=r;else delete next[r.id];}return next;})}/>Select all filtered ({rows.length})</label>{selected.length>0&&<button onClick={()=>setChecked({})}>Clear {selected.length}</button>}</div><small className="wac-help">Selection stays when changing pages. Each phone receives one message.</small>

   <h2>Contacts<small>{kind}</small></h2><div className="wac-contacts">{recipients.isPending&&<p role="status">Loading contacts…</p>}{recipients.isError&&<p role="alert">{whatsappError(recipients.error)} <button onClick={()=>void recipients.refetch()}>Retry</button></p>}{directory.isError&&<p role="alert">WhatsApp details could not load. <button onClick={()=>void directory.refetch()}>Retry details</button></p>}{!recipients.isPending&&!recipients.isError&&!rows.length&&<p>No contacts match your filters.</p>}{rows.map(r=><div key={r.id} className={`wac-contact-row ${focus?.id===r.id?'focused':''}`}><input aria-label={`Select ${recipientName(r)}`} type="checkbox" checked={!!checked[r.id]} onChange={()=>toggle(r)}/><button className={`wac-contact ${focus?.id===r.id?'selected':''}`} onClick={()=>{setFocus(r);if(!Object.keys(checked).length)setChecked({[r.id]:r});}}><span className="wac-avatar">{initials(recipientName(r))}</span><span><strong>{recipientName(r)}</strong><small>{r.phone||'No mobile number'}</small><em>{stageName(r)}</em><small>{metadata(r)?.contact?.consent?.replace(/_/g,' ')||'Consent not recorded'}</small></span></button></div>)}</div>

   <div className="wac-pagination"><button disabled={page===1} onClick={()=>setPage(page-1)}>Previous</button><span>Page {page}</span><button disabled={page*50>=(recipients.data?.total||0)} onClick={()=>setPage(page+1)}>Next</button></div>

  </aside><main className="wac-main">

   <div className="wac-contact-heading"><span className="wac-avatar">{focus?initials(recipientName(focus)):'?'}</span><div><h2>{recipientName(focus)}</h2><p>{focus?`${kind.slice(0,-1)} ID ${focus.id} · ${focus.email||'No email recorded'}`:'Choose a contact to preview its message'}</p></div><div className="wac-contact-meta"><Phone size={18}/><span><strong>{focus?recipientPhone(focus)||'No mobile':'No mobile selected'}</strong><small>Mobile (Primary)</small></span></div><div className="wac-contact-meta"><MessageCircle size={18}/><span><strong>{focusMetadata?.contact?.consent?.replace(/_/g,' ')||'Not recorded'}</strong><small>WhatsApp consent</small></span></div></div>

   {focus&&<div className="wac-quick-details"><span><small>Contact / company</small><strong>{focus.contacts?.find(contact=>contact.id===focus.primaryContactId)?.name||recipientName(focus)}</strong></span><span><small>Owner · stage</small><strong>{ownerName(focus)} · {stageName(focus)}</strong></span><span><small>Outstanding</small><strong>{focusMetadata?.financeAvailable?[...new Set(invoicesFor(focus).map(i=>i.currency))].map(currency=>money(invoicesFor(focus).filter(i=>i.currency===currency).reduce((sum,i)=>sum+Number(i.balance||0),0),currency)).join(' · ')||money(0):'Not available'}</strong></span><span><small>Last communication</small><strong>{focusMetadata?.contact?.lastMessageAt?new Date(focusMetadata.contact.lastMessageAt).toLocaleString():'No activity recorded'}</strong></span></div>}

   <nav className="wac-modes" aria-label="Message type">{modes.map(([label,Icon])=><button key={label} className={mode===label?'active':''} aria-pressed={mode===label} onClick={()=>chooseMode(label)}><Icon size={17}/>{label}</button>)}</nav>

   <div className="wac-stats">{[[Users,selected.length,'Recipients selected'],[Layers,focus?invoicesFor(focus).length:0,'Linked invoices for preview'],[CalendarDays,file?1:0,'Attachment per message'],[CheckCircle2,account.data?.configured?'Connected':'Setup required','WhatsApp sender']].map(([Icon,value,label],i)=>{const Metric=Icon as typeof Users;return <div key={i}><Metric/><span><strong>{String(value)}</strong><small>{String(label)}</small></span></div>;})}</div>

   {account.isError&&<p role="alert">Sender status could not load. <button onClick={()=>void account.refetch()}>Retry</button></p>}{account.data&&!account.data.configured&&<p className="wac-warning">Connect a WhatsApp sender in <Link to="/crm/whatsapp/settings">account settings</Link> before sending.</p>}

   <div className="wac-workspace"><section className="wac-editor"><div className="wac-card-title"><Layers/><div><h2>Configure {mode}</h2><p>Personalize each message, then review your recipients.</p></div></div>

    {isInvoice&&<><div className="wac-fields"><label>Linked invoice<select disabled={!focus} value={focus?invoiceIds[focus.id]||'':''} onChange={e=>{if(focus)setInvoiceIds(previous=>({...previous,[focus.id]:e.target.value}));}}><option value="">Select an invoice for {focus?recipientName(focus):'the preview contact'}</option>{focusInvoices.map(i=><option key={i.id} value={i.id}>{i.name} · {money(i.balance??i.amount,i.currency)}</option>)}</select></label><label>Minimum due amount<input type="number" min="0" value={minimum} placeholder="0" onChange={e=>{setMinimum(e.target.value);setInvoiceIds({});}}/></label><label>Maximum due amount<input type="number" min="0" value={maximum} placeholder="Any amount" onChange={e=>{setMaximum(e.target.value);setInvoiceIds({});}}/></label></div>{minimum&&maximum&&Number(minimum)>Number(maximum)&&<p role="alert">Maximum amount must be at least the minimum.</p>}<div className="wac-date-row"><label>Due date (message only)<input type="date" value={due} onChange={e=>setDue(e.target.value)}/></label><button disabled={directory.isFetching||!entries.length} onClick={()=>void directory.refetch()}><RefreshCw size={16}/>Load invoices</button>{mode==='Send Invoice'&&<button disabled={!invoice||fileBusy||selected.length>1} title={selected.length>1?'Select one recipient to attach its invoice':'Attach the selected invoice PDF'} onClick={()=>void attachInvoice()}><Paperclip size={16}/>{fileBusy?'Loading PDF…':'Attach invoice PDF'}</button>}</div>{selected.length>1&&<div className="wac-bulk-invoices"><strong>Choose the matching invoice for each recipient</strong>{selected.map(r=><label key={r.id}>{recipientName(r)}<select value={invoiceIds[r.id]||''} onChange={e=>setInvoiceIds(previous=>({...previous,[r.id]:e.target.value}))}><option value="">Choose invoice</option>{invoiceOptions(r).map(i=><option key={i.id} value={i.id}>{i.name} · {money(i.balance??i.amount,i.currency)}</option>)}</select></label>)}</div>}</>}

    {mode==='Greetings'&&<label className="wac-template">Occasion<select aria-label="Occasion" value={occasion} onChange={e=>{setOccasion(e.target.value);if(templateKey==='draft')setBody(e.target.value==='General greeting'?drafts.Greetings:`Dear {{contact_name}},\n\nWarm wishes for {{occasion}}! Thank you for being a valued part of our business.`);}}>{['General greeting','Birthday','Anniversary','Festival','New year','Welcome'].map(o=><option key={o}>{o}</option>)}</select></label>}

    {mode==='Follow-up'&&<label className="wac-template">Follow-up date<input type="date" value={followUp} onChange={e=>setFollowUp(e.target.value)}/></label>}

    <div className="wac-template-heading"><label className="wac-check"><input type="checkbox" checked={favoritesOnly} onChange={e=>setFavoritesOnly(e.target.checked)}/>Favourites only</label><button aria-label="Toggle template favourite" aria-pressed={favorites.includes(templateKey==='draft'?`draft:${mode}`:templateKey)} onClick={()=>{const key=templateKey==='draft'?`draft:${mode}`:templateKey;setFavorites(previous=>previous.includes(key)?previous.filter(k=>k!==key):[...previous,key]);}}><Star size={16} fill={favorites.includes(templateKey==='draft'?`draft:${mode}`:templateKey)?'currentColor':'none'}/></button></div>

    <label className="wac-template">Message template<select aria-label="Message template" value={templateKey} onChange={e=>{setTemplateKey(e.target.value);setParameters({});}}><optgroup label="Editable reply drafts"><option value="draft">{mode} - Standard · editable draft</option></optgroup>{['UTILITY','MARKETING','AUTHENTICATION'].map(category=><optgroup key={category} label={`Approved WhatsApp · ${category.toLowerCase()}`}>{approved.filter(t=>t.category===category&&(!favoritesOnly||favorites.includes(`${t.name}:${t.language}`))).map(t=><option key={t.name+t.language} value={`${t.name}:${t.language}`}>{t.name.replace(/_/g,' ')} · {t.language} · approved</option>)}</optgroup>)}</select></label>

    {templates.isError&&<p role="alert">Approved templates could not load. <button onClick={()=>void templates.refetch()}>Retry templates</button></p>}

    {templateKey==='draft'?<><label className="wac-message-label" htmlFor="wac-message">Message <span>*</span></label><div className="wac-message"><div className="wac-editor-toolbar"><span>Editable reply draft · 24-hour window required</span><select aria-label="Insert token" value="" onChange={e=>insertToken(e.target.value)}><option value="">Insert Token</option>{['contact_name','company_name','invoice_number','due_amount','due_date','follow_up_date','occasion'].map(k=><option key={k} value={`{{${k}}}`}>{k.replace(/_/g,' ')}</option>)}</select></div><textarea ref={editor} id="wac-message" value={body} onChange={e=>setBody(e.target.value)} rows={8} maxLength={4096}/></div></>:<div className="wac-approved-fields"><p>Approved template text stays unchanged. Personalize its fields below.</p>{templateFields.map(field=><label key={field}>Value for {field}<input value={parameters[field]||''} placeholder="Text or {{contact_name}}" onChange={e=>setParameters(previous=>({...previous,[field]:e.target.value}))}/></label>)}</div>}

    {missing.length>0&&<div className="wac-missing" role="status"><strong>Complete missing fields</strong>{missing.map(token=><button key={token} onClick={()=>{if(token==='{{due_date}}')document.querySelector<HTMLInputElement>('.wac-date-row input')?.focus();else editor.current?.focus();}}>{token}</button>)}<small>Select the matching invoice, supply a date, or replace the highlighted tokens.</small></div>}

    <div className={`wac-dropzone ${file?'has-file':''}`} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();if(e.dataTransfer.files.length>1)setNotice('WhatsApp supports one attachment per message here. Choose one file.');else addFile(e.dataTransfer.files[0]);}}><Paperclip/><div><strong>{file?file.name:'Drop an attachment here'}</strong><small>{file?`${Math.ceil(file.size/1024)} KB · attached to each selected message`:'PDF, JPG or PNG · one file, up to 16 MB'}</small></div><input ref={fileInput} hidden type="file" accept=".pdf,.jpg,.jpeg,.png" onChange={e=>{addFile(e.target.files?.[0]);e.target.value='';}}/><button onClick={()=>fileInput.current?.click()}>{file?'Replace':'Browse'}</button>{file&&<button aria-label="Remove attachment" onClick={()=>setFile(undefined)}><X size={16}/></button>}</div>{file&&selected.length>1&&<p className="wac-warning">This file goes to every selected recipient. Use a single recipient for an invoice document.</p>}

    <div className="wac-scheduling"><Clock size={18}/><label>Delivery<select aria-label="Delivery" value={delivery} onChange={e=>setDelivery(e.target.value)}><option value="now">Send now</option><option value="schedule">Schedule</option></select></label><button onClick={tomorrow}>Tomorrow, 9 AM</button>{delivery==='schedule'&&<label>Scheduled date and time<input type="datetime-local" value={scheduleTime} min={localDateTime(new Date())} onChange={e=>setScheduleTime(e.target.value)}/></label>}<small>Timezone: {timezone}{delivery==='schedule'?' · Approved templates only. Recipient business hours and communication limits apply.':''}</small></div>

   </section><section className="wac-preview-column"><div className="wac-preview"><h2><MessageCircle/>WhatsApp Preview<small>{kind.slice(0,-1)} View</small></h2><div className="wac-chat"><span className="wac-today">Today</span><div className="wac-bubble">{preview.split(/(\{\{[^}]+\}\})/g).map((part,index)=>missingTokens(part).length?<mark key={index}>{part}</mark>:<Fragment key={index}>{part}</Fragment>)}{file&&<div className="wac-invoice"><FileText/>{file.name}<small>{Math.ceil(file.size/1024)} KB</small></div>}<small>Preview only</small></div></div><p className="wac-help">{focus?`Preview for ${recipientName(focus)}. Select another contact to inspect its personalized message.`:'Select a contact to preview personalization.'}</p></div>{selected.length>0&&<div className="wac-recipient-summary"><h2>Selected recipients · {selected.length}</h2>{selected.slice(0,8).map(r=><button key={r.id} onClick={()=>setFocus(r)}><span>{recipientName(r)}</span><small>{missingTokens(previewFor(r)).length?'Missing fields':'Ready for validation'}</small></button>)}{selected.length>8&&<p>+{selected.length-8} more in review</p>}</div>}</section></div>

   {notice&&<p className="wac-warning" role="status">{notice}</p>}

   <footer className="wac-sticky-actions"><div><strong>{selected.length} recipient{selected.length===1?'':'s'} · {file?1:0} attachment{file?'':'s'}</strong><small>{delivery==='schedule'?scheduleTime?`${new Date(scheduleTime).toLocaleString()} · ${timezone}`:'Choose a delivery time':'Send now'}</small></div><Link to="/crm/delivery-logs"><Layers size={17}/>Open Queue</Link><button className="wac-primary" disabled={!readyToReview} onClick={openReview}><Send size={17}/>{delivery==='schedule'?'Review & Schedule':'Review & Send'}{selected.length>0?` (${selected.length})`:''}</button></footer>

   {results.length>0&&<section className="wac-results"><div className="wac-results-heading"><h2>Delivery results</h2><button onClick={()=>void outcomes.refetch()}><RefreshCw size={15}/>Refresh status</button></div><div className="wac-result-counts">{['accepted','sent','delivered','read','queued','failed'].map(status=><button key={status} aria-pressed={resultFilter===status} onClick={()=>setResultFilter(resultFilter===status?'all':status)}><strong>{visibleResults.filter(r=>r.status===status).length}</strong>{status}</button>)}</div><label>Show results<select value={resultFilter} onChange={e=>setResultFilter(e.target.value)}><option value="all">All results</option><option value="issues">Needs attention</option>{[...new Set(visibleResults.map(r=>r.status))].map(status=><option key={status} value={status}>{status.replace(/_/g,' ')}</option>)}</select></label><div className="wac-result-list">{displayedResults.map(result=><article key={result.key}><div><strong>{result.name}</strong><small>{result.payload.to}</small></div><span className={`wac-result-status is-${result.status}`}>{result.status.replace(/_/g,' ')}</span>{result.dueAt&&<time>{new Date(result.dueAt).toLocaleString()}</time>}{(result.error||result.message?.errorCode)&&<p>{result.error||`Provider error ${result.message?.errorCode}`}</p>}{result.status==='failed'&&!result.message?.providerMessageId&&!result.scheduledId&&<button onClick={()=>void retry(result)}>Review retry</button>}{['submitting','reserved','reconciliation_required','schedule_unconfirmed'].includes(result.status)&&<button onClick={()=>void outcomes.refetch()}>Check original request</button>}{result.scheduledId&&['failed','blocked'].includes(result.status)&&<button onClick={async()=>{try{await api.post(`/communication/customers/deliveries/${result.scheduledId}/retry`);void outcomes.refetch();}catch(error){setNotice(whatsappError(error));}}}>Retry queued delivery</button>}</article>)}</div></section>}

  </main></div>{review&&<CommunicationSendReview {...review} scope={scope} onClose={()=>{setReview(undefined);void directory.refetch();}} onResult={recordResult}/>} 

 </section>;

}

