import { NativeSelect } from "@/components/ui/native-select";
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { recordScope, useRecordScope } from '@/shared/records/Record360Workspace';
import { api } from '@/services/api';
import { Button } from '@/components/ui/button';
import { useQuery } from '@tanstack/react-query';

export const centerBase='/communication/engagement';
export function useCenterScope(){
  // Subscribe to context events, but keep persisted draft/preference keys stable.
  useRecordScope();
  const user=useAuthStore(s=>s.user);
  return recordScope(user);
}
export function usePreference<T,>(key:string,initial:T){
  const scope=useCenterScope(),storageKey=`communication:${scope}:${key}`;
  const read=():T=>{try{return JSON.parse(localStorage.getItem(storageKey)||'null')??initial;}catch{return initial;}};
  const [state,setState]=useState(()=>({key:storageKey,value:read()}));
  const value=state.key===storageKey?state.value:read();
  const setValue=(next:T|((previous:T)=>T))=>setState({key:storageKey,value:typeof next==='function'?(next as (previous:T)=>T)(value):next});
  useEffect(()=>{if(state.key!==storageKey)setState({key:storageKey,value:read()});},[storageKey,state.key]);
  useEffect(()=>{if(state.key===storageKey)try{localStorage.setItem(storageKey,JSON.stringify(state.value));}catch{/* Continue in memory when browser storage is unavailable. */}},[storageKey,state]);
  return [value,setValue] as const;
}
export function EmptyState({title,description,to,label}:{title:string;description:string;to?:string;label?:string}){return <div className="cc-empty"><h3>{title}</h3><p>{description}</p>{to&&<Button asChild variant="outline"><Link to={to}>{label||'Get started'}</Link></Button>}</div>;}
export const errorText=(e:unknown)=>{const detail=(e as {response?:{data?:{detail?:unknown}}})?.response?.data?.detail;return typeof detail==='string'?detail:'This action could not be completed. Your changes are retained.';};
export type PickedRecord={id:number;entity:string;name:string;email?:string;phone?:string};
export function RecordPicker({value,onChange,label='Find a CRM record',types=['lead','contact','deal']}:{value:PickedRecord|null;onChange:(value:PickedRecord|null)=>void;label?:string;types?:string[]}){
  const scope=useCenterScope();const [kind,setKind]=useState(types[0]),[search,setSearch]=useState(''),[term,setTerm]=useState('');
  useEffect(()=>{const timer=setTimeout(()=>setTerm(search.trim()),250);return()=>clearTimeout(timer);},[search]);
  const records=useQuery({queryKey:['center-record-picker',scope,kind,term],enabled:term.length>=2,queryFn:async()=>(await api.get<{items:PickedRecord[]}>(centerBase+'/records',{params:{kind,search:term}})).data.items});
  return <div className="cc-record-picker"><label>{label}<div className="cc-input-pair"><NativeSelect aria-label={`${label} type`} value={kind} onChange={e=>{setKind(e.target.value);setSearch('');}}>{types.map(type=><option key={type} value={type}>{type}</option>)}</NativeSelect><input aria-label={label} placeholder="Search name, phone or email" value={search} onChange={e=>setSearch(e.target.value)}/></div></label>{value&&<div className="cc-selected-record"><span>{value.name} · {value.entity} #{value.id}</span><button type="button" aria-label={`Clear ${label}`} onClick={()=>onChange(null)}>Clear</button></div>}{records.isFetching&&<p role="status">Searching CRM…</p>}{records.isError&&<p role="alert">{errorText(records.error)}</p>}{term.length>=2&&!records.isFetching&&records.data?.length===0&&<p role="status">No matching records. Try another name or number.</p>}{search&&records.data&&<div className="cc-picker-results" aria-label="Matching CRM records">{records.data.map(record=><button type="button" key={record.id} onClick={()=>{onChange(record);setSearch('');setTerm('');}}><strong>{record.name}</strong><small>{record.email||record.phone||record.entity} · #{record.id}</small></button>)}</div>}</div>;
}
export function DeliveryEvidence({kind,id}:{kind:'whatsapp'|'email';id:number}){
  const [open,setOpen]=useState(false);const scope=useCenterScope();
  const evidence=useQuery({queryKey:['center-evidence',scope,kind,id],enabled:open,queryFn:async()=>(await api.get(centerBase+`/delivery/${kind}/${id}`)).data});
  return <div className="cc-delivery-evidence"><button type="button" aria-expanded={open} onClick={()=>setOpen(!open)}>Delivery details {open?'−':'+'}</button>{open&&<div>{evidence.isPending&&<p role="status">Loading delivery events…</p>}{evidence.isError&&<p role="alert">{errorText(evidence.error)}</p>}{evidence.data&&<><ol>{evidence.data.events.map((event:{status:string;at:string;errorCode?:string},index:number)=><li key={index}><strong>{event.status.replace(/_/g,' ')}</strong><time>{new Date(event.at).toLocaleString()}</time>{event.errorCode&&<span>Provider code {event.errorCode}</span>}</li>)}</ol><p>{evidence.data.guidance}</p><Link to={kind==='whatsapp'?'/crm/whatsapp/sent':'/crm/delivery-logs'}>Open delivery workspace</Link></>}</div>}</div>;
}

type Snippet={name:string;text:string;favorite:boolean};
const defaultSnippets:Snippet[]=[{name:'Welcome',text:'Thank you for contacting us. How can we help you today?',favorite:true},{name:'Checking your request',text:'Thank you for the details. I am checking your request and will update you here.',favorite:false},{name:'Request details',text:'Could you share your order or service request reference so we can assist you?',favorite:false}];
export function QuickReplies({onInsert,disabled=false}:{onInsert:(text:string)=>void;disabled?:boolean}){
  const [open,setOpen]=useState(false),[search,setSearch]=useState(''),[name,setName]=useState(''),[text,setText]=useState('');
  const [snippets,setSnippets]=usePreference<Snippet[]>('quick-replies',defaultSnippets);
  return <details className="cc-quick-replies" open={open} onToggle={e=>setOpen(e.currentTarget.open)}><summary>Quick replies <kbd>/</kbd></summary><div><input aria-label="Search quick replies" value={search} placeholder="Search saved replies" onChange={e=>setSearch(e.target.value)}/>{[...snippets].sort((a,b)=>Number(b.favorite)-Number(a.favorite)).filter(s=>(s.name+' '+s.text).toLowerCase().includes(search.toLowerCase())).map(snippet=><div className="cc-snippet" key={snippet.name}><button type="button" disabled={disabled} onClick={()=>{onInsert(snippet.text);setOpen(false);}}><strong>{snippet.name}</strong><small>{snippet.text}</small></button><button type="button" aria-label={`${snippet.favorite?'Unfavorite':'Favorite'} ${snippet.name}`} onClick={()=>setSnippets(snippets.map(s=>s.name===snippet.name?{...s,favorite:!s.favorite}:s))}>{snippet.favorite?'★':'☆'}</button></div>)}<details><summary>Save a new reply</summary><label>Reply name<input maxLength={80} value={name} onChange={e=>setName(e.target.value)}/></label><label>Reply text<textarea maxLength={4096} value={text} onChange={e=>setText(e.target.value)}/></label><Button type="button" size="sm" disabled={!name.trim()||!text.trim()||snippets.some(s=>s.name===name.trim())} onClick={()=>{setSnippets([...snippets,{name:name.trim(),text:text.trim(),favorite:false}]);setName('');setText('');}}>Save reply</Button></details><small>Reply suggestions are editable. WhatsApp text replies still require an open service window.</small></div></details>;
}
