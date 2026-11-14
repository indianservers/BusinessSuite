import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { Button } from "@/components/ui/button";
import { useDebounced, type Company } from "@/shared/master-data/CompanySelect";
import SmartRecordPicker from "./SmartRecordPicker";
import Record360Workspace, { recordError, useRecordScope } from "./Record360Workspace";

export default function Customer360Page({source="crm"}: {source?:"crm"|"srm"}) {
  usePageTitle("Customer 360");
  const scope=useRecordScope(),[params,setParams]=useSearchParams();
  const [search,setSearch]=useState("");const term=useDebounced(search);
  const raw=params.get("customer")||"",id=/^[1-9]\d*$/.test(raw)&&Number.isSafeInteger(Number(raw))?Number(raw):undefined;
  const options=useInfiniteQuery({queryKey:["customer-360-picker",scope,source,term],initialPageParam:1,
    queryFn:({pageParam,signal})=>api.get<{items:Company[];total:number}>("/master-data/companies",{params:{source,role:"Customer",entity_kind:"all",search:term,page:pageParam,per_page:30},signal}).then(r=>r.data),
    getNextPageParam:(last,pages)=>last.total>pages.length*30?pages.length+1:undefined,retry:false,staleTime:30000});
  const selected=useQuery({queryKey:["customer-360-selected",scope,source,id],enabled:!!id,retry:false,
    queryFn:({signal})=>api.get<Company>(`/master-data/companies/${id}`,{params:{source},signal}).then(r=>r.data)});
  const items=[...new Map((options.data?.pages.flatMap(page=>page.items)||[]).map(row=>[row.id,row])).values()];
  const suggestion=(row:Company)=>({id:String(row.id),label:row.name,description:[row.email,row.phone].filter(Boolean).join(" · "),record:row});
  const choose=(value?:number)=>setParams(current=>{const next=new URLSearchParams(current);if(value)next.set("customer",String(value));else next.delete("customer");return next;});
  return <main className="space-y-4 p-4 md:p-6">
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="page-title">Customer 360</h1><p className="page-description">Deals, orders, invoices and activities for one customer, within your access.</p></div><Button asChild variant="outline"><Link to={`/${source}/customers`}>Manage customers</Link></Button></header>
    <section aria-label="Choose customer" className="max-w-xl"><SmartRecordPicker name="Customer" value={selected.data?String(id):""} search={search} onSearch={setSearch} items={items.map(suggestion)} selected={selected.data?suggestion(selected.data):undefined}
      onSelect={row=>{choose(row.id);setSearch("");}} onClear={()=>choose()} loading={options.isFetching} error={options.isError?recordError(options.error):undefined} retry={()=>void options.refetch()} hasMore={options.hasNextPage} loadMore={()=>void options.fetchNextPage()}/></section>
    {raw&&!id&&<p role="alert">Choose a valid customer.</p>}
    {id&&selected.isPending&&<p role="status">Loading customer…</p>}
    {id&&selected.isError&&<div role="alert">{recordError(selected.error)} <Button variant="outline" onClick={()=>void selected.refetch()}>Retry customer</Button></div>}
    {!raw&&<p>Select a customer to see their linked work and history.</p>}
    {id&&selected.data&&<Record360Workspace key={`${scope}:${source}:${id}`} kind="company" id={id} source={source}/>}
  </main>;
}
