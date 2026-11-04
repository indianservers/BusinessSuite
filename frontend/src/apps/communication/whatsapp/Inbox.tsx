import PhoneActions from "@/components/PhoneActions";
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { Search, MessageCircle, Link2, UserRound, PanelRightOpen, X, ArrowLeft, ChevronLeft, ChevronRight, Check, CheckCheck, Clock3, Copy, ShieldCheck, Inbox as InboxIcon, ArrowUpRight } from 'lucide-react';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import Composer from './Composer';
import LinkConversation from './LinkConversation';
import RecipientConsent from './RecipientConsent';
import { whatsappBase as base, whatsappError, contactName, initials, shortTime, type Contact, type Message, type Template } from './types';

function Avatar({contact}:{contact:Contact}) {return <span className={`wa-avatar wa-avatar-${contact.id%5}`} aria-hidden="true">{initials(contact.name||'#')}<MessageCircle size={11}/></span>;}
function DeliveryMark({status}:{status:string}) {return ['read','delivered'].includes(status)?<CheckCheck size={14} className={status==='read'?'wa-read':''}/>:status==='sent'||status==='accepted'?<Check size={13}/>:<Clock3 size={12}/>;}
function dayLabel(value:string) {const date=new Date(value);return date.toDateString()===new Date().toDateString()?'Today':date.toLocaleDateString([],{weekday:'short',day:'numeric',month:'short',year:'numeric'});}

export default function Inbox({scope,selected,onSelect,onClear,templates,admin,refresh}:{scope:string;selected:number|null;onSelect:(id:number)=>void;onClear:()=>void;templates:Template[];admin:boolean;refresh:()=>Promise<void>}) {
  const [search,setSearch]=useState(''),[term,setTerm]=useState(''),[filter,setFilter]=useState('all');
  const [before,setBefore]=useState<number|undefined>(),[historyBefore,setHistoryBefore]=useState<number|undefined>();
  const [detailsOpen,setDetailsOpen]=useState(()=>window.matchMedia('(min-width:1351px)').matches);
  const transcript=useRef<HTMLDivElement>(null),atBottom=useRef(true);
  const workspace=useRef<HTMLDivElement>(null);
  const [workspaceHeight,setWorkspaceHeight]=useState<number>();
  useLayoutEffect(()=>{
    const fit=()=>{if(workspace.current)setWorkspaceHeight(Math.max(360,window.innerHeight-workspace.current.getBoundingClientRect().top-14));};
    fit();window.addEventListener('resize',fit);
    return()=>window.removeEventListener('resize',fit);
  },[]);
  const navigate=useNavigate();
  useEffect(()=>{const media=window.matchMedia('(min-width:1351px)');const change=(event:MediaQueryListEvent)=>setDetailsOpen(event.matches);media.addEventListener('change',change);return()=>media.removeEventListener('change',change);},[]);
  useEffect(()=>{const timer=setTimeout(()=>{setTerm(search);setBefore(undefined);},250);return()=>clearTimeout(timer);},[search]);
  useEffect(()=>{setHistoryBefore(undefined);atBottom.current=true;},[selected]);
  const conversations=useQuery({queryKey:['whatsapp',scope,'conversations',before,term,filter],queryFn:async()=>(await api.get<{items:Contact[];nextBefore:number|null}>(base+'/conversations',{params:{before,search:term,linked:filter==='all'?undefined:filter==='linked'}})).data,refetchInterval:15000});
  const history=useQuery({queryKey:['whatsapp',scope,'history',selected,historyBefore],enabled:selected!==null,queryFn:async()=>(await api.get<{contact:Contact;items:Message[];nextBefore:number|null}>(base+`/conversations/${selected}/messages`,{params:{before:historyBefore}})).data,refetchInterval:10000});
  const lastId=history.data?.items[history.data.items.length-1]?.id;
  useEffect(()=>{if(atBottom.current&&transcript.current)transcript.current.scrollTop=transcript.current.scrollHeight;},[lastId,selected]);
  const contact=history.data?.contact;
  const contacts=[...(conversations.data?.items||[])].sort((a,b)=>new Date(b.lastMessage?.createdAt||b.lastMessageAt||0).getTime()-new Date(a.lastMessage?.createdAt||a.lastMessageAt||0).getTime());
  return <div ref={workspace} style={workspaceHeight?{height:workspaceHeight}:undefined} className={`wa-inbox-layout ${selected?'wa-has-selection':''} ${contact?'wa-with-contact':''} ${detailsOpen?'wa-details-open':''}`}>
    <aside className="wa-conversations"><div className="wa-list-heading"><span className="wa-feature-icon"><InboxIcon size={20}/></span><div><h3>WhatsApp Inbox & Delivery</h3><p>Conversations, replies & delivery</p></div></div>
      <label className="wa-conversation-search"><Search size={15}/><input aria-label="Search conversations" placeholder="Search name or number…" value={search} onChange={e=>setSearch(e.target.value)}/>{search&&<button aria-label="Clear conversation search" onClick={()=>setSearch('')}><X size={13}/></button>}</label>
      <div className="wa-list-filters" role="group" aria-label="Filter conversations">{[['all','All'],['linked','CRM linked'],['unlinked','Unlinked']].map(([key,label])=><button key={key} aria-pressed={filter===key} className={filter===key?'is-active':''} onClick={()=>{setFilter(key);setBefore(undefined);}}>{label}{filter===key&&conversations.data&&<span title="Conversations on this page">{conversations.data.items.length}</span>}</button>)}</div>
      <div className="wa-conversation-scroll">
        {conversations.isPending&&<p className="wa-empty-note">Loading conversations…</p>}
        {conversations.isError&&<p role="alert" className="wa-error">{whatsappError(conversations.error)}</p>}
        {contacts.map(item=><button key={item.id} className={`wa-conversation-row ${selected===item.id?'is-selected':''}`} onClick={()=>{onSelect(item.id);setHistoryBefore(undefined);setDetailsOpen(window.matchMedia('(min-width:1351px)').matches);}} aria-label={`Open conversation with ${contactName(item)}`} aria-current={selected===item.id?'true':undefined}>
          <Avatar contact={item}/><span className="wa-conversation-copy"><span className="wa-conversation-name"><strong>{contactName(item)}</strong><time>{shortTime(item.lastMessage?.createdAt||item.lastMessageAt)}</time></span><span className="wa-conversation-phone">+{item.recipient}{item.entityType&&<b>{item.entityType}</b>}</span><span className="wa-conversation-snippet">{item.lastMessage?.direction==='outbound'&&<DeliveryMark status={item.lastMessage.status}/>}<span>{item.lastMessage?.body||'Open conversation'}</span></span></span>
        </button>)}
        {conversations.data&&!conversations.data.items.length&&<div className="wa-list-empty"><Search size={25}/><p>{term?'No matching conversations.':'No conversations in this view yet.'}</p><small>{term?'Try a name or international number.':'Incoming messages appear here when they reach this business number.'}</small></div>}
      </div><div className="wa-conversation-pagination"><span>{conversations.data?.items.length||0} on this page</span>{before&&<button onClick={()=>setBefore(undefined)}><ChevronLeft size={13}/>Latest</button>}{conversations.data?.nextBefore&&<button onClick={()=>setBefore(conversations.data!.nextBefore!)}>Older<ChevronRight size={13}/></button>}</div>
    </aside>
    <section className="wa-chat-pane" aria-label="Conversation">
      {!selected&&<div className="wa-chat-empty"><span><MessageCircle size={34}/></span><h3>Your conversations, in one place</h3><p>Select a conversation to read messages, reply, or check delivery.</p><small>Only messages recorded after webhook setup appear here.</small></div>}
      {selected&&history.isPending&&<p className="wa-empty-note">Loading conversation…</p>}
      {history.isError&&<p role="alert" className="wa-error">{whatsappError(history.error)}</p>}
      {contact&&<><header className="wa-chat-heading"><button className="wa-mobile-back wa-icon-button" aria-label="Back to conversations" onClick={onClear}><ArrowLeft size={17}/></button><Avatar contact={contact}/><div className="wa-chat-title"><h3>{contactName(contact)}</h3><p><PhoneActions value={"+" + contact.recipient} /></p></div>{contact.entityId&&<span className="wa-linked-badge"><Link2 size={12}/>CRM linked</span>}<button className="wa-icon-button wa-details-toggle" aria-label="Contact details" aria-expanded={detailsOpen} onClick={()=>setDetailsOpen(!detailsOpen)}><PanelRightOpen size={18}/></button></header>
        <div className="wa-chat-transcript" ref={transcript} onScroll={e=>{const el=e.currentTarget;atBottom.current=el.scrollHeight-el.scrollTop-el.clientHeight<100;}}>
          <div className="wa-history-pagination">{historyBefore&&<button onClick={()=>{setHistoryBefore(undefined);atBottom.current=true;}}>Latest messages</button>}{history.data?.nextBefore&&<button onClick={()=>{setHistoryBefore(history.data!.nextBefore!);atBottom.current=false;}}>Earlier messages</button>}</div>
          {history.data?.items.map((message,index,messages)=>{const day=dayLabel(message.createdAt);return <div key={message.id} className="wa-message-group">{(!index||dayLabel(messages[index-1].createdAt)!==day)&&<div className="wa-day-separator"><span>{day}</span></div>}<article className={`wa-bubble ${message.direction==='outbound'?'is-outgoing':'is-incoming'}`}><p>{message.body}</p><footer><time dateTime={message.createdAt}>{new Date(message.createdAt).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time>{message.direction==='outbound'&&<span className="wa-message-delivery" title={message.status} aria-label={`Delivery: ${message.status}`}><span>{message.status.replace(/_/g,' ')}</span><DeliveryMark status={message.status}/></span>}</footer>{message.errorCode&&<small className="wa-error">Meta code {message.errorCode}</small>}</article></div>;})}
          {history.data&&!history.data.items.length&&<p className="wa-empty-note">No messages on this page.</p>}
        </div><Composer key={contact.id} scope={scope} contact={contact} templates={templates} admin={admin} refresh={refresh} compact/>
      </>}
    </section>
    {contact&&<aside className="wa-contact-inspector"><div className="wa-inspector-heading"><LayersIcon/><h3>CRM & Contact Details</h3><button className="wa-icon-button wa-close-inspector" aria-label="Close contact details" onClick={()=>setDetailsOpen(false)}><X size={16}/></button></div>
      {contact.entityId&&<Link className="wa-crm-record-link" to={`/crm/${contact.entityType==='lead'?'leads':contact.entityType==='deal'?'deals':'contacts'}/${contact.entityId}`}><Link2 size={17}/><span><small>Linked {contact.entityType} #{contact.entityId}</small><strong>{contactName(contact)}</strong></span><ArrowUpRight size={15}/></Link>}
      <ContactDetails contact={contact}/>
      {admin&&<LinkConversation key={contact.id} contactId={contact.id} refresh={refresh}/>}
      <div className="wa-inspector-section"><h4><ShieldCheck size={14}/>Consent & reply window</h4><span className={`wa-window-badge ${contact.serviceWindowOpen?'is-open':''}`}><Clock3 size={12}/>{contact.serviceWindowOpen?'Reply window open':'Reply window closed'}</span>{contact.serviceWindowEndsAt&&<p className="wa-muted-note">{contact.serviceWindowOpen?'Until':'Last window ended'} {new Date(contact.serviceWindowEndsAt).toLocaleString()}</p>}<RecipientConsent to={'+'+contact.recipient} entityType={contact.entityType} entityId={contact.entityId} disabled={!admin&&!contact.entityId} refresh={refresh}/></div>
      <div className="wa-inspector-section wa-next-actions"><h4>Next actions</h4><button onClick={()=>navigate('/crm/whatsapp/templates')}><ShieldCheck size={14}/>Manage approved templates<ArrowUpRight size={13}/></button><button onClick={()=>navigate('/crm/whatsapp/sent')}><CheckCheck size={14}/>View delivery status<ArrowUpRight size={13}/></button></div>
    </aside>}
  </div>;
}
function LayersIcon(){return <Link2 size={18}/>;}
function ContactDetails({contact}:{contact:Contact}) {
  const [copied,setCopied]=useState(false);
  return <section className="wa-contact-card"><div className="wa-contact-identity"><Avatar contact={contact}/><div><strong>{contactName(contact)}</strong><small><PhoneActions value={"+" + contact.recipient} /></small></div><button className="wa-icon-button" aria-label="Copy contact number" onClick={()=>void navigator.clipboard.writeText('+'+contact.recipient).then(()=>setCopied(true)).catch(()=>setCopied(false))}><Copy size={14}/></button></div>{copied&&<p className="wa-muted-note" role="status">Number copied</p>}<dl><div><dt>Record type</dt><dd>{contact.entityType||'Not linked'}</dd></div><div><dt>Source</dt><dd>WhatsApp</dd></div><div><dt>Consent</dt><dd>{contact.consent.replace(/_/g,' ')}</dd></div>{contact.consentSource&&<div><dt>Evidence</dt><dd>{contact.consentSource}</dd></div>}</dl></section>;
}
