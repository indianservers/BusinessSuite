import {useEffect,useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import SmartRecordPicker from '@/shared/records/SmartRecordPicker';
import {Button} from '@/components/ui/button';
import {api} from '@/services/api';
import {useRecordScope} from '@/lib/record-scope';
import {catalogApi,catalogError,offeringKinds,useDebounced,type CatalogItem,type CatalogSource} from './api';

export type Beneficiary={id:number;name:string;email?:string;phone?:string};

/** Share the existing directory picker; never require a customer ID to be typed. */
export function BeneficiaryPicker({source,value,onChange,limit}:{source:CatalogSource;value:Beneficiary[];onChange:(rows:Beneficiary[])=>void;limit:number}){
 const scope=useRecordScope(),masterSource=source==='pms'?'project_management':source;
 const [search,setSearch]=useState(''),term=useDebounced(search),[page,setPage]=useState(1),[enabled,setEnabled]=useState(false);
 const owner=JSON.stringify([scope,source,term]);
 const [loaded,setLoaded]=useState<{owner:string;items:Beneficiary[]}>({owner:'',items:[]});
 const query=useQuery<{items:Beneficiary[];total:number}>({queryKey:['plan-beneficiary-picker',scope,masterSource,term,page],enabled,queryFn:({signal})=>api.get('/master-data/companies',{params:{source:masterSource,entity_kind:'all',search:term,page,per_page:50},signal}).then(r=>r.data),retry:false,staleTime:30000});
 useEffect(()=>{if(query.data)setLoaded(previous=>({owner,items:page===1||previous.owner!==owner?query.data!.items:[...new Map([...previous.items,...query.data!.items].map(row=>[row.id,row])).values()]}));},[query.data,owner,page]);
 const options=(loaded.owner===owner?loaded.items:[]).filter(row=>!value.some(selected=>selected.id===row.id));
 return <section className="sc-section" aria-label="Plan beneficiaries"><h3>Beneficiaries</h3><p className="sc-muted">Selected {value.length} of {limit}. Choose existing customer records by name, email or phone.</p>{value.map(row=><div className="sc-preview-line" key={row.id}><span><strong>{row.name}</strong><small>{[row.email,row.phone].filter(Boolean).join(' · ')}</small></span><Button size="sm" variant="ghost" type="button" aria-label={`Remove beneficiary ${row.name}`} onClick={()=>onChange(value.filter(item=>item.id!==row.id))}>Remove</Button></div>)}{value.length<limit?<div onFocusCapture={()=>setEnabled(true)}><SmartRecordPicker name="Beneficiary" value="" search={search} onSearch={next=>{setSearch(next);setPage(1);}} items={options.map(row=>({id:String(row.id),label:row.name,description:[row.email,row.phone].filter(Boolean).join(' · '),record:row}))} onSelect={row=>{if(!value.some(item=>item.id===row.id)&&value.length<limit)onChange([...value,row]);}} onClear={()=>setSearch('')} loading={query.isFetching} error={query.isError?catalogError(query.error):undefined} retry={()=>void query.refetch()} hasMore={!!query.data&&page*50<query.data.total} loadMore={()=>setPage(current=>current+1)}/></div>:<p className="sc-muted">Beneficiary limit reached. Remove a selection to choose someone else.</p>}</section>;
}

/** Hydrate selected IDs through the existing scoped, kind-aware catalog API. */
export function EligibleOfferingPicker({source,value,onChange}:{source:CatalogSource;value:number[];onChange:(ids:number[])=>void}){
 const scope=useRecordScope(),[search,setSearch]=useState(''),term=useDebounced(search),[page,setPage]=useState(1),[enabled,setEnabled]=useState(false);
 const owner=JSON.stringify([scope,source,term]),[loaded,setLoaded]=useState<{owner:string;items:CatalogItem[]}>({owner:'',items:[]});
 const query=useQuery({queryKey:['plan-eligible-picker',scope,source,term,page],enabled,queryFn:({signal})=>api.get<{items:CatalogItem[];total:number}>('/catalog/items',{params:{source,search:term,page,per_page:50,status:'Active'},signal,recordCache:false}).then(r=>r.data),retry:false,staleTime:30000});
 const selectedKey=value.join(',');
 const selected=useQuery({queryKey:['plan-eligible-selected',scope,source,selectedKey],enabled:value.length>0,queryFn:async()=>{
  const rows:CatalogItem[]=[];
  for(let offset=0;offset<value.length;offset+=100){const keys=value.slice(offset,offset+100).flatMap(id=>offeringKinds.map(kind=>`${kind}:${id}`)).join(',');const {data}=await catalogApi.list(source,{item_keys:keys,status:'all',per_page:100});rows.push(...data.items);}
  return rows;
 },retry:false,staleTime:30000});
 useEffect(()=>{if(query.data)setLoaded(previous=>({owner,items:page===1||previous.owner!==owner?query.data!.items:[...new Map([...previous.items,...query.data!.items].map(row=>[row.id,row])).values()]}));},[query.data,owner,page]);
 const options=(loaded.owner===owner?loaded.items:[]).filter(row=>!value.includes(row.id));
 const names=new Map([...(selected.data||[]),...(loaded.owner===owner?loaded.items:[])].map(row=>[row.id,row]));
 return <div aria-label="Eligible offerings"><p className="sc-muted">Eligible products and services. No selection means all offerings are allowed by this rule.</p>{value.map((id,index)=>{const row=names.get(id),label=row?`${row.name} · ${row.code}${row.status==='Archived'?' (Archived)':''}`:selected.isFetching?'Loading selected offering…':`Unavailable offering ${index+1}`;return <div className="sc-preview-line" key={id}><span>{label}</span><Button type="button" size="sm" variant="ghost" aria-label={`Remove eligible offering ${row?.name||index+1}`} onClick={()=>onChange(value.filter(current=>current!==id))}>Remove</Button></div>;})}{selected.isError&&<p role="alert" className="sc-error">Selected offering names could not load. Existing restrictions are preserved. <button type="button" onClick={()=>void selected.refetch()}>Retry</button></p>}{value.length<500&&<div onFocusCapture={()=>setEnabled(true)}><SmartRecordPicker name="Eligible offering" value="" search={search} onSearch={next=>{setSearch(next);setPage(1);}} placeholder="Search offering name or code…" items={options.map(row=>({id:String(row.id),label:row.name,description:`${row.kind} · ${row.code}`,record:row}))} onSelect={row=>{if(!value.includes(row.id))onChange([...value,row.id]);}} onClear={()=>setSearch('')} loading={query.isFetching} error={query.isError?catalogError(query.error):undefined} retry={()=>void query.refetch()} hasMore={!!query.data&&page*50<query.data.total} loadMore={()=>setPage(current=>current+1)}/></div>}</div>;
}
