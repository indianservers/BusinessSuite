import { useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ArrowLeft, ArrowRight, CalendarDays, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import './mobile-schedule-agenda.css';

type Booking = { appointment_id:number; employee_id:number; employee_name:string; service_name:string; starts_at:string; ends_at:string; planned_minutes:number; status:string };
export default function MobileScheduleAgenda<T extends Booking>({items,zone,day,onDay,onSelect,filters,loading,error,onRefresh,hasMore,onMore}:{items:T[];zone:string;day:string;onDay:(day:string)=>void;onSelect:(item:T)=>void;filters:ReactNode;loading:boolean;error?:string;onRefresh:()=>void;hasMore?:boolean;onMore:()=>void}) {
  const [all,setAll]=useState(false),[page,setPage]=useState(0),[size,setSize]=useState(1),[filterOpen,setFilterOpen]=useState(false);
  const list=useRef<HTMLDivElement>(null);
  const date=(value:string)=>new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date(value));
  const dayOf=(value:string)=>{const parts=date(value);return ['year','month','day'].map(key=>parts.find(p=>p.type===key)?.value).join('-');};
  const visible=useMemo(()=>items.filter(item=>all||dayOf(item.starts_at)===day).sort((a,b)=>Date.parse(a.starts_at)-Date.parse(b.starts_at)),[items,day,zone,all]);
  const pages=Math.max(1,Math.ceil(visible.length/size)),current=Math.min(page,pages-1);
  useLayoutEffect(()=>setPage(0),[day,all,items]);
  useLayoutEffect(()=>{
    const node=list.current;if(!node)return;
    const measure=()=>{const heights=[...node.querySelectorAll<HTMLElement>('.mobile-schedule-card')].map(card=>{if(!card.hidden)return card.getBoundingClientRect().height;const copy=card.cloneNode(true) as HTMLElement;copy.hidden=false;Object.assign(copy.style,{position:'absolute',visibility:'hidden',width:`${node.clientWidth}px`,left:'-10000px'});node.append(copy);const height=copy.getBoundingClientRect().height;copy.remove();return height;});const tallest=Math.max(92,...heights);setSize(Math.max(1,Math.floor((node.clientHeight+8)/(tallest+8))));};
    const observer=new ResizeObserver(measure);observer.observe(node);measure();return()=>observer.disconnect();
  },[visible]);
  const shift=(amount:number)=>{const next=new Date(day+'T12:00:00Z');next.setUTCDate(next.getUTCDate()+amount);onDay(next.toISOString().slice(0,10));};
  const time=(value:string)=>new Intl.DateTimeFormat('en-IN',{timeZone:zone,hour:'numeric',minute:'2-digit'}).format(new Date(value));
  const nextDay=items.map(item=>dayOf(item.starts_at)).sort().find(value=>value>day);
  return <section className="mobile-schedule-agenda" data-srm-native-pages="true" aria-label="Mobile scheduled bookings">
    <div className="mobile-schedule-toolbar"><strong>{items.length} bookings loaded</strong><button aria-label="Refresh bookings" onClick={onRefresh} disabled={loading}><RefreshCw size={17}/></button><button aria-label="Schedule filters" onClick={()=>setFilterOpen(true)}><SlidersHorizontal size={17}/></button></div>
    <div className="mobile-schedule-views" role="group" aria-label="Mobile schedule view"><button aria-pressed={!all} onClick={()=>setAll(false)}><CalendarDays size={15}/>Calendar</button><button aria-pressed={all} onClick={()=>setAll(true)}>All bookings</button></div>
    {!all&&<div className="mobile-schedule-date"><button aria-label="Previous day" onClick={()=>shift(-1)}><ArrowLeft size={16}/></button><input aria-label="Calendar day" type="date" value={day} onChange={event=>onDay(event.target.value)}/><button aria-label="Next day" onClick={()=>shift(1)}><ArrowRight size={16}/></button></div>}
    <small className="mobile-schedule-zone">{zone}{!all&&` · ${visible.length} bookings on this day`}</small>
    {loading&&<p role="status">Refreshing bookings…</p>}{error&&<p role="alert">{error}</p>}
    <div ref={list} className="mobile-schedule-cards" role="region" aria-label="Paginated scheduled bookings">
      {visible.map((item,index)=><button hidden={index<current*size||index>=(current+1)*size} className="mobile-schedule-card" key={`${item.appointment_id}:${item.employee_id}`} onClick={()=>onSelect(item)} aria-label={`Open booking ${item.appointment_id}`}><span><strong>{item.service_name}</strong><em>{item.status.replace(/_/g,' ')}</em></span><span>{item.employee_name}</span><span><b>{all?`${dayOf(item.starts_at)} · `:''}{time(item.starts_at)} – {time(item.ends_at)}</b><small>{item.planned_minutes} min</small></span></button>)}
      {!visible.length&&!loading&&<div className="mobile-schedule-empty"><CalendarDays/><strong>No bookings {all?'in this range':'on this day'}</strong>{nextDay&&!all&&<button onClick={()=>onDay(nextDay)}>Next booked day · {nextDay}</button>}</div>}
    </div>
    {pages>1&&<nav className="mobile-schedule-pages" aria-label="Booking pages"><button aria-label="Previous booking page" disabled={!current} onClick={()=>setPage(current-1)}><ArrowLeft size={17}/></button><span>{current*size+1}–{Math.min((current+1)*size,visible.length)} of {visible.length} · {current+1}/{pages}</span><button aria-label="Next booking page" disabled={current>=pages-1} onClick={()=>setPage(current+1)}><ArrowRight size={17}/></button></nav>}
    {hasMore&&<button onClick={onMore}>Load more bookings</button>}
    <Dialog open={filterOpen} onOpenChange={setFilterOpen}><DialogContent className="mobile-schedule-filter-dialog"><DialogTitle>Schedule filters</DialogTitle><DialogDescription>Filter the loaded range by employee, service or status.</DialogDescription>{filters}<button onClick={()=>setFilterOpen(false)}>Show bookings</button></DialogContent></Dialog>
  </section>;
}
