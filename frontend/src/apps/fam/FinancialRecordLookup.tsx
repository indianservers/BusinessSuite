import {useEffect,useRef,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import SmartRecordPicker,{type RecordSuggestion} from '@/shared/records/SmartRecordPicker';
import {Input} from '@/components/ui/input';
import {useAuthStore} from '@/store/authStore';
import {selectedBranch} from '@/lib/branch-context';
import {api} from '@/services/api';
import type {FAMRecord} from './types';
/** Optional authorized names; direct IDs and parent conversion remain unchanged. */
export default function FinancialRecordLookup({kind,value,onChange,disabled=false,id,'aria-label':manualLabel}:{kind:'vendor'|'ledger';value:string;onChange:(value:string)=>void;disabled?:boolean;id?:string;'aria-label'?:string}){
 const user=useAuthStore(state=>state.user),[manual,setManual]=useState(false),[search,setSearch]=useState('');
 const root=useRef<HTMLDivElement>(null),modeFocus=useRef(false);
 useEffect(()=>{if(modeFocus.current){modeFocus.current=false;root.current?.querySelector<HTMLInputElement>(manual?"input":"[data-record-picker]")?.focus();}},[manual]);
 const grant=user?.access?.grants?.fam;
 const scope=JSON.stringify([user?.id,user?.access?.companyId,sessionStorage.getItem('suite-tenant'),sessionStorage.getItem('suite-organization'),selectedBranch(),user?.role,user?.is_superuser,grant?.enabled,grant?.permissions.slice().sort(),grant?.actions.slice().sort()]);
 useEffect(()=>{setSearch('');},[scope]);
 const query=useQuery({queryKey:['fam','mobile-record-options',kind,scope],enabled:!!user&&!manual,staleTime:300000,retry:false,placeholderData:()=>undefined,queryFn:async({signal})=>{
  const response=await api.get<{items:FAMRecord[]}>(kind==='vendor'?'/fam/parties?party_type=vendor':'/fam/ledgers',{signal,recordCache:false});
  if(!Array.isArray(response.data.items))throw Error('Choices could not be loaded.');
  return response.data.items;
 }});
 const items:RecordSuggestion<FAMRecord>[]=(query.isError?[]:query.data||[]).filter(row=>kind!=='vendor'||!row.party_type||['vendor','both'].includes(String(row.party_type))).map(row=>({id:String(row.id),label:String(kind==='vendor'?row.legal_name||row.trade_name||row.id:row.ledger_name||row.id),description:[kind==='vendor'?row.party_code:row.ledger_code,kind==='vendor'?row.email:row.nature,kind==='vendor'?row.phone||row.mobile:row.ledger_type,row.active===false?'Inactive':null,`#${row.id}`].filter(Boolean).join(' · '),searchText:kind==='vendor'?[row.trade_name,row.email,row.phone,row.mobile,row.gstin].filter(Boolean).join(' '):undefined,record:row}));
 const choiceValue=value==="0"?"":value;
 const selected=items.find(item=>item.id===choiceValue);
 return <div ref={root} className="fam-financial-record-lookup"><fieldset disabled={disabled}>
  {manual?<Input id={id} aria-label={manualLabel||`${kind} ID`} inputMode="numeric" value={value} onChange={event=>onChange(event.target.value)}/>:<SmartRecordPicker inputId={id} name={kind} value={choiceValue} search={search} onSearch={setSearch} items={items} selected={selected} onSelect={row=>onChange(String(row.id))} onClear={()=>onChange('')} loading={query.isFetching} error={query.isError?(disabled?'Names could not be loaded.':'Choices are unavailable. You can enter the ID or retry.'):undefined} retry={disabled?undefined:()=>void query.refetch()}/>}
  {!manual&&selected&&<p className="fam-financial-selected-name">{selected.label} · #{selected.id}</p>}
  <button type="button" className="fam-financial-lookup-mode" onPointerDown={event=>event.preventDefault()} onClick={()=>{modeFocus.current=true;setManual(!manual);setSearch('');}}>{manual?'Choose by name':`Enter ${kind} ID`}</button>
 </fieldset>{disabled&&query.isError&&<button type="button" className="fam-financial-lookup-mode" onClick={()=>void query.refetch()}>Retry names</button>}</div>;
}
