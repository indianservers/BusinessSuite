import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { NativeSelect } from "@/components/ui/native-select";
import SmartRecordPicker from "./SmartRecordPicker";
import { recordError, useRecordScope } from "./Record360Workspace";

type Item = {id:number;kind:"contact"|"lead";record_id:number;name:string;url:string};
export default function TaskRecordLinks({taskId}:{taskId:number}){
  const scope=useRecordScope(),cache=useQueryClient();
  const [kind,setKind]=useState<"contact"|"lead">("contact"),[search,setSearch]=useState(""),[term,setTerm]=useState(""),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  useEffect(()=>{const timer=setTimeout(()=>{setTerm(search);},200);return()=>clearTimeout(timer);},[search]);
  const base=`/project-management/task-workspace/tasks/${taskId}`;
  const links=useQuery<{items:Item[];can_manage:boolean}>({queryKey:["task-crm-links",scope,taskId],queryFn:async({signal})=>(await api.get(`${base}/crm-links`,{signal})).data,retry:false});
  const choices=useInfiniteQuery({queryKey:["task-crm-link-options",scope,taskId,kind,term],initialPageParam:0,enabled:links.data?.can_manage===true,queryFn:async({signal,pageParam}):Promise<{items:{id:number;name:string}[];next:number|null}> =>(await api.get(`${base}/crm-link-options`,{params:{kind,search:term,after:pageParam},signal})).data,getNextPageParam:page=>page.next??undefined,retry:false});
  const suggestions=[...new Map((choices.data?.pages.flatMap(page=>page.items)||[]).map(row=>[row.id,row])).values()];
  async function change(work:()=>Promise<unknown>){setBusy(true);setError("");try{await work();await cache.invalidateQueries({queryKey:["task-crm-links"]});void cache.invalidateQueries({queryKey:["record-360-work"]});void cache.invalidateQueries({queryKey:["record-360-events"]});}catch(e){setError(recordError(e));}finally{setBusy(false);}}
  return <section aria-label="Task contacts and leads"><h3>Contacts & leads</h3>{links.isPending&&<p role="status">Loading links…</p>}{links.isError&&<p role="alert">{recordError(links.error)} <button onClick={()=>void links.refetch()}>Retry</button></p>}
    {links.data?.items.map(item=><div key={item.id} className="flex items-center justify-between gap-2 my-2"><Link to={item.url}>{item.name} · {item.kind}</Link>{links.data.can_manage&&<Button type="button" size="sm" variant="ghost" aria-label={`Unlink ${item.name}`} disabled={busy} onClick={()=>void change(()=>api.delete(`${base}/crm-links/${item.id}`))}>Unlink</Button>}</div>)}
    {links.data?.can_manage&&<div className="space-y-2"><label>Link existing <NativeSelect aria-label="CRM link type" value={kind} disabled={busy} onChange={e=>{setKind(e.target.value as typeof kind);setSearch("");setTerm("");}}><option value="contact">Contact</option><option value="lead">Lead</option></NativeSelect></label>{!busy&&<SmartRecordPicker name={kind} value="" search={search} onSearch={setSearch} items={suggestions.map(row=>({id:String(row.id),label:row.name,record:row}))} onSelect={row=>void change(()=>api.post(`${base}/crm-links`,{kind,record_id:row.id}))} onClear={()=>setSearch("")} loading={choices.isFetching} error={choices.isError?recordError(choices.error):undefined} retry={()=>void choices.refetch()} hasMore={choices.hasNextPage} loadMore={()=>void choices.fetchNextPage()}/>}</div>}
    {error&&<p role="alert">{error}</p>}
  </section>;
}
