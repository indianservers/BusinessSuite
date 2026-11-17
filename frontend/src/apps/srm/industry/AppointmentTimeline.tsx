import AppointmentPaymentStatus from "@/shared/scheduling/BookingUX";
import type { ReactNode } from "react";

import { bookingLanes } from "@/shared/scheduling/booking-view";

import { candidates } from '@/shared/scheduling/booking-time';

import type { BookingSlot } from '@/shared/scheduling/PrebookingFields';

import { useMemo, useState } from 'react';

import { CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, Clock3, DoorOpen, UserRound } from 'lucide-react';

import { Button } from '@/components/ui/button';

import { useBusinessTerms } from '@/hooks/use-business-terms';



type Row = {id:number; revision?:number; title:string; status:string; data:Record<string, string | number | number[]>};

const providers = new Set(['provider','doctor','stylist','consultant','technician','employee']);

function localDay(value: string, zone: string) { return new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value)); }

function move(day: string, amount: number) { const date = new Date(day+'T12:00:00Z'); date.setUTCDate(date.getUTCDate()+amount); return date.toISOString().slice(0,10); }

export default function AppointmentTimeline({rows, resources, onSelect, onSlot, showPayments=false, day, onDay, week, onWeek, zone: suppliedZone, actions}: {showPayments?:boolean;day:string;onDay:(day:string)=>void;week:boolean;onWeek:(week:boolean)=>void;zone?:string;actions?:ReactNode;rows:Row[]; resources:Row[]; onSelect:(id:number)=>void; onSlot?:(slot:BookingSlot)=>void}) {

  const {term} = useBusinessTerms();

  const zone = suppliedZone || String(resources.find(row=>providers.has(String(row.data.resource_type)))?.data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone);

  const setDay=onDay, setWeek=onWeek;

  const [resourceView,setResourceView] = useState(false);

  const days = Array.from({length:week?7:1},(_,i)=>move(day,i));

  const visible = rows.filter(row=>row.data.starts_at && days.includes(localDay(String(row.data.starts_at),zone)));

  const columns = useMemo(()=>resources.filter(row=>row.status==='active' && (resourceView ? !providers.has(String(row.data.resource_type)) : providers.has(String(row.data.resource_type)))),[resources,resourceView]);

  const time = (value:string)=>new Intl.DateTimeFormat(undefined,{timeZone:zone,hour:'numeric',minute:'2-digit'}).format(new Date(value));

  const minute = (value:string)=>{const parts=new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value));return Number(parts.find(p=>p.type==='hour')?.value)*60+Number(parts.find(p=>p.type==='minute')?.value);};

  const clockMinutes = (value: unknown) => typeof value === 'string' && /^\d{2}:\d{2}(?::\d{2})?$/.test(value) ? Number(value.slice(0,2))*60+Number(value.slice(3)) : undefined;

  const opens = resources.map(row=>clockMinutes(row.data.opens)).filter((value):value is number=>value!==undefined);

  const closes = resources.map(row=>clockMinutes(row.data.closes)).filter((value):value is number=>value!==undefined);

  const opening = Math.min(...(opens.length ? opens : [9*60]),...visible.map(row=>minute(String(row.data.starts_at))));

  const closing = Math.max(...(closes.length ? closes : [18*60]),...visible.map(row=>minute(String(row.data.starts_at))+Number(row.data.duration_minutes)));

  const height=(closing-opening)*1.25;

  const lanes=week?days.map(value=>({id:value,title:new Intl.DateTimeFormat(undefined,{timeZone:'UTC',weekday:'short',day:'numeric'}).format(new Date(value+'T12:00:00Z'))})):columns;

  return <section className="appointment-timeline" aria-label="Appointment timeline">

    <div className="appointment-timeline-toolbar">{actions}<Button variant="outline" size="icon" aria-label="Previous date" onClick={()=>setDay(move(day,week?-7:-1))}><ChevronLeft size={17}/></Button><label><CalendarDays size={17}/><input aria-label="Timeline date" type="date" value={day} onChange={e=>setDay(e.target.value)}/></label><Button variant="outline" size="icon" aria-label="Next date" onClick={()=>setDay(move(day,week?7:1))}><ChevronRight size={17}/></Button><Button variant="outline" onClick={()=>setDay(localDay(new Date().toISOString(),zone))}>Today</Button><Button variant={!week?'default':'outline'} onClick={()=>setWeek(false)}>Day</Button><Button variant={week?'default':'outline'} onClick={()=>setWeek(true)}>Week</Button><Button variant={!resourceView?'default':'outline'} onClick={()=>setResourceView(false)}><UserRound size={16}/>{term('provider',true)}</Button><Button variant={resourceView?'default':'outline'} onClick={()=>setResourceView(true)}><DoorOpen size={16}/>{term('resource',true)}</Button></div>

    <p className="appointment-timeline-zone">{zone} · Loaded bookings only. Refresh to check the latest reservations.</p>

    <div className="appointment-timeline-scroll"><div className="appointment-timeline-columns" style={{gridTemplateColumns:`76px repeat(${Math.max(1,lanes.length)},minmax(150px,1fr))`}}>

      <div className="appointment-timeline-header"><Clock3 size={17}/>Time</div>{lanes.map(lane=><div key={lane.id} className="appointment-timeline-header"><span className="appointment-avatar">{resourceView?<DoorOpen size={20}/>:lane.title.split(' ').slice(0,2).map(word=>word[0]).join('')}</span><strong>{lane.title}</strong></div>)}

      <div className="appointment-time-axis" style={{height}}>{Array.from({length:Math.ceil((closing-opening)/30)+1},(_,i)=><span key={i} style={{top:i*30*1.25}}>{String(Math.floor((opening+i*30)/60)%12||12)}:{String((opening+i*30)%60).padStart(2,'0')} {(opening+i*30)<720?'AM':'PM'}</span>)}</div>

      {lanes.map(lane=><div key={lane.id} className="appointment-timeline-lane" style={{height}}>{onSlot && Array.from({length:Math.ceil((closing-opening)/30)},(_,i)=>opening+i*30).map(minute => {

        const date = week ? String(lane.id) : day;

        const at = candidates(`${date}T${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`,zone);

        const resource = resources.find(r => r.id === Number(lane.id));

        if (at.length !== 1 || at[0] <= Date.now() || visible.some(row => !['cancelled','no_show','completed'].includes(row.status) && (week ? localDay(String(row.data.starts_at),zone)===lane.id : (row.data.resource_ids as number[] || []).includes(Number(lane.id))) && Date.parse(String(row.data.starts_at)) < at[0]+30*60000 && Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000 > at[0])) return null;

        return <button key={`slot-${minute}`} type="button" className="appointment-empty-slot" aria-label={`Prebook ${lane.title} at ${date} ${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`} style={{top:(minute-opening)*1.25,height:37.5}} onClick={()=>onSlot({startsAt:new Date(at[0]).toISOString(),...(resource ? providers.has(String(resource.data.resource_type)) ? {employeeId:Number(resource.data.employee_id)} : {resourceId:resource.id} : {}),key:crypto.randomUUID()})}/>;

      })}{bookingLanes(visible.filter(row=>week?localDay(String(row.data.starts_at),zone)===lane.id:(row.data.resource_ids as number[]||[]).includes(Number(lane.id)))).map(({item:row,lane:column,count})=><button key={row.id} type="button" data-status={row.status} data-compact={Number(row.data.duration_minutes)<45} className="appointment-timeline-booking" title={`${row.data.customer_name || row.title} · ${row.data.service_name} · ${time(String(row.data.starts_at))} · ${row.status}`} aria-label={`${row.data.customer_name || row.title}, ${row.data.service_name}, ${time(String(row.data.starts_at))} to ${time(new Date(Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000).toISOString())}, ${row.status}`} style={{top:(minute(String(row.data.starts_at))-opening)*1.25,height:Math.max(32,Number(row.data.duration_minutes)*1.25-4),left:`calc(${column/count*100}% + 3px)`,width:`calc(${100/count}% - 6px)`,right:"auto"}} onClick={()=>onSelect(row.id)}><strong>{String(row.data.customer_name||row.title)}</strong><span>{String(row.data.service_name||'Service')}</span><span><CalendarDays size={14}/>{time(String(row.data.starts_at))} – {time(new Date(Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000).toISOString())}</span><small>{row.status.replace(/_/g,' ')}</small>{showPayments && <AppointmentPaymentStatus id={row.id} revision={row.revision || 1} enabled compact/>}</button>)}</div>)}

      {!lanes.length&&<p className="p-4 text-sm">No configured {resourceView?term('resource',true):term('provider',true)} available in this view.</p>}

    </div></div><div className="appointment-timeline-legend"><span><CalendarDays size={15}/>Confirmed</span><span><Clock3 size={15}/>In progress</span><span><CheckCircle2 size={15}/>Completed</span></div>

  </section>;

}

