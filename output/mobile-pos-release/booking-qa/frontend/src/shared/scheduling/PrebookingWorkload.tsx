import {useState} from 'react';
import {useInfiniteQuery,type InfiniteData} from '@tanstack/react-query';
import {api} from '@/services/api';
import {useRecordScope} from '@/lib/record-scope';
import {candidates,wall} from './booking-time';
type Interval=[number,number];
type WorkPage={items:{appointment_id?:number;starts_at:string;ends_at:string;status:string}[];next_cursor:string|null};
type WorkloadPage={items:{appointment_id?:number;starts_at:string;ends_at:string;status:string}[];next_cursor:string|null};

export function mergeIntervals(intervals:Interval[]):Interval[]{const merged:Interval[]=[];for(const [a,b] of [...intervals].filter(([a,b])=>Number.isFinite(a)&&b>a).sort((a,b)=>a[0]-b[0])){const last=merged.at(-1);if(last&&a<=last[1])last[1]=Math.max(last[1],b);else merged.push([a,b]);}return merged;}
export default function PrebookingWorkload({employeeId,date,zone,slots,minutes,current}:{employeeId:number;date:string;zone:string;slots:{starts_at:string}[];minutes:number;current:boolean}){
 const [open,setOpen]=useState(false),scope=useRecordScope();
 const start=candidates(`${date}T00:00`,zone)[0],next=date?new Date(Date.parse(`${date}T12:00Z`)+86400000).toISOString().slice(0,10):'',end=candidates(`${next}T00:00`,zone)[0];
 const query=useInfiniteQuery<WorkloadPage>({queryKey:['prebooking-workload',scope,employeeId,start,end],initialPageParam:undefined as string|undefined,getNextPageParam:page=>page.next_cursor || undefined,enabled:open&&!!start&&!!end,retry:false,queryFn:({signal,pageParam})=>api.get<WorkloadPage>(`/employees/${employeeId}/planned-services`,{recordCache:false,signal,params:{from_at:new Date(start).toISOString(),until_at:new Date(end).toISOString(),limit:100,cursor:pageParam}}).then(r=>r.data)});
 const items=[...new Map((query.data?.pages.flatMap(p=>p.items)||[]).map(r=>[r.appointment_id || `${r.starts_at}:${r.ends_at}:${r.status}`,r])).values()];
 const intervals:Interval[]=items.filter(r=>!['cancelled','no_show'].includes(r.status)).map(r=>[Math.max(start,Date.parse(r.starts_at)),Math.min(end,Date.parse(r.ends_at))]);
 const occupied=mergeIntervals(intervals),summed=intervals.reduce((n,[a,b])=>n+Math.max(0,b-a)/60000,0),busy=occupied.reduce((n,[a,b])=>n+(b-a)/60000,0);
 const free=mergeIntervals(slots.map(s=>[Date.parse(s.starts_at),Date.parse(s.starts_at)+minutes*60000]));
 const timeline=[...occupied.map(([a,b])=>({a,b,label:'Booked'})),...(current?free.map(([a,b])=>({a,b,label:'Available service window'})):[])].sort((a,b)=>a.a-b.a);
 return <details className="prebooking-workload" onToggle={e=>setOpen(e.currentTarget.open)}><summary>Employee workload and free windows</summary><p>{date} · {zone}. Planned services only; this does not represent attendance or all employee duties.</p>{query.isPending?<p role="status">Loading permitted work…</p>:query.isError?<p>Workload is restricted or unavailable. <button type="button" onClick={()=>void query.refetch()}>Retry workload</button></p>:<><p>{(summed/60).toFixed(1)} booked hours in permitted records; {(busy/60).toFixed(1)} occupied clock hours{query.hasNextPage?' (partial; load remaining records)':''}.</p><small>Service hours sum each record; occupied hours count overlapping time once.</small>{query.hasNextPage&&<button type="button" disabled={query.isFetchingNextPage} onClick={()=>void query.fetchNextPage()}>Load more workload records</button>}{query.isFetchNextPageError&&<p role="alert">More workload records could not load. Retry loading more.</p>}</>}<strong>Available service windows</strong>{!current?<p>Choose complete details and refresh availability to see current windows.</p>:!free.length?<p>No verified service windows for these resources and duration.</p>:null}<ol className="prebooking-day-timeline" aria-label="Combined daily workload">{timeline.map(({a,b,label},i)=><li key={`${a}:${label}:${i}`} data-kind={label==='Booked'?'booked':'free'}><span>{wall(a,zone).slice(11)}–{wall(b,zone).slice(11)}</span><strong>{label}</strong></li>)}</ol></details>;
}
