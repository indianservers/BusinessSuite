import { useEffect, useRef, useState } from 'react';
import { api } from '@/services/api';
import { NativeSelect } from '@/components/ui/native-select';

type Entry={id:number;command:string;status:string;plan:{summary:string}|null};
const statuses=['awaiting_approval','needs_clarification','planning','queued','executing','waiting_pms','paused','failed','needs_reconciliation','succeeded','answered','cancelled','cancelling','superseded'];

export default function RequestHistory<T extends Entry>({workspace,revision,busy,onSelect}:{workspace:string;revision:number;busy:boolean;onSelect:(run:T)=>void}){
  const [search,setSearch]=useState(''),[status,setStatus]=useState(''),[refresh,setRefresh]=useState(0);
  const [items,setItems]=useState<T[]>([]),[cursor,setCursor]=useState<number|null>(null);
  const [loading,setLoading]=useState(false),[error,setError]=useState('');
  const epoch=useRef(0);
  useEffect(()=>{
    const current=++epoch.current,controller=new AbortController();
    setItems([]);setCursor(null);setError('');setLoading(true);
    const timer=setTimeout(()=>{
      api.get('/ai-operator/suite/runs',{signal:controller.signal,params:{workspace_id:workspace||undefined,search:search.trim()||undefined,status:status||undefined,limit:12}})
        .then(response=>{if(current===epoch.current){setItems(response.data.items);setCursor(response.data.has_more?response.data.next_before_id:null);}})
        .catch(()=>{if(current===epoch.current&&!controller.signal.aborted)setError('Request history could not load. Refresh to try again.');})
        .finally(()=>{if(current===epoch.current)setLoading(false);});
    },250);
    return()=>{epoch.current++;clearTimeout(timer);controller.abort();};
  },[workspace,revision,search,status,refresh]);
  async function more(){
    if(!cursor||loading)return;
    const current=epoch.current;setLoading(true);setError('');
    try{
      const response=await api.get('/ai-operator/suite/runs',{params:{workspace_id:workspace||undefined,search:search.trim()||undefined,status:status||undefined,before_id:cursor,limit:12}});
      if(current!==epoch.current)return;
      setItems(previous=>{const ids=new Set(previous.map(row=>row.id));return [...previous,...response.data.items.filter((row:T)=>!ids.has(row.id))];});
      setCursor(response.data.has_more?response.data.next_before_id:null);
    }catch{if(current===epoch.current)setError('More requests could not load. Try again.');}
    finally{if(current===epoch.current)setLoading(false);}
  }
  return <section className="space-y-3 rounded-xl border bg-card p-4" aria-label="Request history">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-semibold">Recent requests</h2><button type="button" className="text-xs underline" disabled={loading||busy} onClick={()=>setRefresh(value=>value+1)}>Refresh history</button></div>
    <input aria-label="Search request history" type="search" className="w-full rounded border bg-background p-2 text-sm" maxLength={200} value={search} onChange={event=>setSearch(event.target.value)} placeholder="Search request, summary or #ID"/>
    <NativeSelect aria-label="Request status filter" className="w-full rounded border bg-background p-2 text-sm" value={status} onChange={event=>setStatus(event.target.value)}><option value="">All statuses</option>{statuses.map(value=><option key={value} value={value}>{value.replace(/_/g,' ')}</option>)}</NativeSelect>
    {items.map(row=><button type="button" disabled={busy} key={row.id} onClick={()=>onSelect(row)} className="block w-full rounded-lg border p-3 text-left text-sm"><span className="block truncate">{row.plan?.summary||row.command||`Request #${row.id}`}</span><small className="text-muted-foreground">#{row.id} · {row.status.replace(/_/g,' ')}</small></button>)}
    {!loading&&!error&&!items.length&&<p role="status" className="text-sm text-muted-foreground">No matching requests.</p>}
    {loading&&<p role="status" className="text-sm">Loading request history…</p>}
    {error&&<p role="alert" className="text-sm text-destructive">{error}</p>}
    {cursor!==null&&<button type="button" disabled={loading||busy} className="rounded border px-3 py-2 text-sm" onClick={()=>void more()}>Load older requests</button>}
  </section>;
}
