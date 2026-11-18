import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import { api } from '@/services/api';
import { useRecordScope } from '@/lib/record-scope';
import { dealError } from '@/apps/crm/deals/deal-utils';
type Customer={id:number;name:string;email?:string;phone?:string};
/** Reviewed selected-pack projection of the canonical CRM customer; no master creation/editing. */
export default function ConstructionCustomerSelect({value,onChange}:{value:string;onChange:(id:string)=>void}){
 const scope=useRecordScope(),[search,setSearch]=useState(''),[term,setTerm]=useState(''),[after,setAfter]=useState(0),[items,setItems]=useState<Customer[]>([]);
 useEffect(()=>{const timer=setTimeout(()=>{setTerm(search.trim());setAfter(0);},250);return()=>clearTimeout(timer);},[search]);
 const query=useQuery({queryKey:['construction-customer-options',scope,term,after],retry:false,queryFn:async({signal})=>(await api.get<{items:Customer[];next:number|null}>('/srm/pos/customers',{params:{search:term,after,limit:50},signal})).data});
 useEffect(()=>{if(query.data)setItems(previous=>after===0?query.data.items:[...new Map([...previous,...query.data.items].map(item=>[item.id,item])).values()]);},[query.data,after]);
 const selected=useQuery({queryKey:['construction-customer-option',scope,value],enabled:!!value,retry:false,queryFn:async({signal})=>(await api.get<Customer>(`/srm/pos/customers/${value}`,{signal})).data});
 const option=(row:Customer)=>({id:String(row.id),label:row.name,description:[row.email,row.phone].filter(Boolean).join(' · '),record:row});
 return <SmartRecordPicker name="Existing customer" value={value} search={search} onSearch={setSearch} items={items.map(option)} selected={selected.data?option(selected.data):undefined} onSelect={row=>{onChange(String(row.id));setSearch('');}} onClear={()=>{onChange('');setSearch('');}} loading={query.isFetching} error={query.isError?dealError(query.error):selected.isError?dealError(selected.error):undefined} retry={()=>{void query.refetch();if(value)void selected.refetch();}} hasMore={query.data?.next!=null} loadMore={()=>{if(query.data?.next!=null)setAfter(query.data.next);}} />;
}
