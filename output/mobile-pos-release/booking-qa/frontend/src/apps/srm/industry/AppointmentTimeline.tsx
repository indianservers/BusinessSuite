import { Dialog, DialogContent, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import ReferenceField from '@/shared/scheduling/ReferenceField';
import AppointmentPaymentStatus from "@/shared/scheduling/BookingUX";

import type { ReactNode } from "react";



import { bookingLanes } from "@/shared/scheduling/booking-view";



import { candidates } from '@/shared/scheduling/booking-time';



import type { BookingSlot } from '@/shared/scheduling/PrebookingFields';



import { useEffect, useMemo, useState } from 'react';



import { CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, Clock3, DoorOpen, UserRound, SlidersHorizontal, List, Search, XCircle, Layers3, Tag, Activity, AlignStartVertical, FlagTriangleRight, Scissors, MessageCircle, Flower2, Armchair, BedDouble, Presentation } from 'lucide-react';



import { Button } from '@/components/ui/button';



import { useBusinessTerms } from '@/hooks/use-business-terms';







type Row = {id:number; revision?:number; title:string; status:string; data:Record<string, string | number | number[]>};



const providers = new Set(['provider','doctor','stylist','consultant','technician','employee']);



function statusLabel(status:string){return ({booked:'Confirmed',checked_in:'Checked in',completed:'Completed',in_service:'In service',cancelled:'Cancelled',no_show:'No show',pending:'Pending'} as Record<string,string>)[status] || status.replace(/_/g,' ');}
function BookingStateIcon({status}:{status:string}){const Icon=status==='booked'?CalendarDays:status==='pending'?Clock3:status==='cancelled'?XCircle:CheckCircle2;return <Icon size={15} className="appointment-state-icon" data-status={status}/>;}
function ServiceIcon({name}:{name:string}){const Icon=/hair|styling|cut/i.test(name)?Scissors:/therapy/i.test(name)?Flower2:/consult/i.test(name)?MessageCircle:Tag;return <Icon size={19}/>;}
function PhysicalIcon({resource}:{resource?:Row}){const type=resource?.data.resource_type,title=resource?.title || '';const Icon=type==='chair'?Armchair:/treatment/i.test(title)?BedDouble:/meeting/i.test(title)?Presentation:DoorOpen;return <Icon size={20}/>;}
function localDay(value: string, zone: string) { return new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value)); }



function move(day: string, amount: number) { const date = new Date(day+'T12:00:00Z'); date.setUTCDate(date.getUTCDate()+amount); return date.toISOString().slice(0,10); }



export default function AppointmentTimeline({rows, resources, onSelect, onSlot, showPayments=false, day, onDay, week, onWeek, zone: suppliedZone, actions}: {showPayments?:boolean;day:string;onDay:(day:string)=>void;week:boolean;onWeek:(week:boolean)=>void;zone?:string;actions?:ReactNode;rows:Row[]; resources:Row[]; onSelect:(id:number)=>void; onSlot?:(slot:BookingSlot)=>void}) {



  const {term} = useBusinessTerms();



  const zone = suppliedZone || String(resources.find(row=>providers.has(String(row.data.resource_type)))?.data.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone);



  const setDay=onDay, setWeek=onWeek;



  const [resourceView,setResourceView] = useState(false);

  const [view,setView] = useState<'List'|'Calendar'|'Gantt'>(()=>window.matchMedia('(max-width: 767px)').matches?'Calendar':'Gantt');

  const [search,setSearch] = useState('');

  const [employee,setEmployee] = useState('');

  const [asset,setAsset] = useState(()=>new URLSearchParams(window.location.search).get('resource_id') || '');
  const [now,setNow]=useState(Date.now());
  useEffect(()=>{const timer=setInterval(()=>setNow(Date.now()),60000);return()=>clearInterval(timer);},[]);

  const [service,setService] = useState('');

  const [status,setStatus] = useState('');
  const [mobileFilters,setMobileFilters]=useState(false);



  const days = Array.from({length:week?7:1},(_,i)=>move(day,i));



  const visible = rows.filter(row=>row.data.starts_at && days.includes(localDay(String(row.data.starts_at),zone)) && `${row.data.customer_name || row.title} ${row.data.service_name}`.toLowerCase().includes(search.toLowerCase()) && (!employee || (row.data.resource_ids as number[] || []).includes(Number(employee))) && (!asset || (row.data.resource_ids as number[] || []).includes(Number(asset))) && (!service || row.data.service_name===service) && (!status || row.status===status));



  const columns = useMemo(()=>resources.filter(row=>row.status==='active' && (resourceView ? !providers.has(String(row.data.resource_type)) : providers.has(String(row.data.resource_type)))),[resources,resourceView]);



  const time = (value:string)=>new Intl.DateTimeFormat(undefined,{timeZone:zone,hour:'numeric',minute:'2-digit'}).format(new Date(value));



  const minute = (value:string)=>{const parts=new Intl.DateTimeFormat('en-GB',{timeZone:zone,hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(value));return Number(parts.find(p=>p.type==='hour')?.value)*60+Number(parts.find(p=>p.type==='minute')?.value);};



  const clockMinutes = (value: unknown) => typeof value === 'string' && /^\d{2}:\d{2}(?::\d{2})?$/.test(value) ? Number(value.slice(0,2))*60+Number(value.slice(3,5)) : undefined;



  const opens = resources.map(row=>clockMinutes(row.data.opens)).filter((value):value is number=>value!==undefined);



  const closes = resources.map(row=>clockMinutes(row.data.closes)).filter((value):value is number=>value!==undefined);



  const opening = Math.min(...(opens.length ? opens : [9*60]),...visible.map(row=>minute(String(row.data.starts_at))));



  const closing = Math.max(...(closes.length ? closes : [18*60]),...visible.map(row=>minute(String(row.data.starts_at))+Number(row.data.duration_minutes)));



  const height=(closing-opening)*1.25;
  const nowMinute=minute(new Date(now).toISOString());
  const showNow=day===localDay(new Date(now).toISOString(),zone)&&nowMinute>=opening&&nowMinute<closing;



  const lanes=week?days.map(value=>({id:value,title:new Intl.DateTimeFormat(undefined,{timeZone:'UTC',weekday:'short',day:'numeric'}).format(new Date(value+'T12:00:00Z'))})):columns;



  return <section className="appointment-timeline" aria-label="Appointment timeline">



    <div className="appointment-reference-datebar"><div className="appointment-date-navigation"><Button variant="outline" size="icon" aria-label="Previous date" onClick={()=>setDay(move(day,week?-7:-1))}><ChevronLeft size={17}/></Button><ReferenceField type="date" aria-label="Timeline date" icon={false} chevron={false} value={day} onChange={e=>{if(e.target.value)setDay(e.target.value);}}/><Button variant="outline" size="icon" aria-label="Next date" onClick={()=>setDay(move(day,week?7:1))}><ChevronRight size={17}/></Button><Button variant="outline" onClick={()=>setDay(localDay(new Date().toISOString(),zone))}>Today</Button><ReferenceField type="date" wrapperClassName="appointment-select-date" aria-label="Select schedule date" text="Select date" value={day} onChange={e=>{if(e.target.value)setDay(e.target.value);}}/></div><div className="appointment-reference-counts">{[{label:'scheduled',icon:CalendarDays,count:visible.length},{label:'checked in',icon:CheckCircle2,count:visible.filter(r=>r.status==='checked_in').length},{label:'completed',icon:FlagTriangleRight,count:visible.filter(r=>r.status==='completed').length},{label:'cancelled',icon:XCircle,count:visible.filter(r=>r.status==='cancelled').length}].map(({label,icon:Icon,count})=><span key={label} data-kind={label}><Icon size={18}/><b>{count}</b> {label}</span>)}</div><div className="appointment-reference-actions">{actions}</div></div>

    <div className="appointment-mobile-week">{Array.from({length:7},(_,i)=>{const start=new Date(day+'T12:00:00Z').getUTCDay();const date=move(day,i-((start+6)%7));return <button key={date} aria-pressed={date===day} onClick={()=>setDay(date)}><span>{new Intl.DateTimeFormat('en',{weekday:'short',timeZone:'UTC'}).format(new Date(date+'T12:00:00Z'))}</span><strong>{Number(date.slice(-2))}</strong></button>;})}</div><div className="appointment-reference-filters"><Button className="appointment-mobile-filter-toggle" variant="ghost" aria-label="Schedule filters" onClick={()=>setMobileFilters(true)}><SlidersHorizontal size={19}/></Button><label><Search size={18}/><input aria-label="Search customer" placeholder="Search customer..." value={search} onChange={e=>setSearch(e.target.value)}/></label><label className="appointment-filter-select"><UserRound size={19}/><select aria-label="Filter employee" value={employee} onChange={e=>setEmployee(e.target.value)}><option value="">Employee</option>{resources.filter(r=>providers.has(String(r.data.resource_type))).map(r=><option key={r.id} value={r.id}>{r.title}</option>)}</select></label><label className="appointment-filter-select"><Layers3 size={19}/><select aria-label="Filter resource" value={asset} onChange={e=>setAsset(e.target.value)}><option value="">Resource</option>{resources.filter(r=>!providers.has(String(r.data.resource_type))).map(r=><option key={r.id} value={r.id}>{r.title}</option>)}</select></label><label className="appointment-filter-select"><Tag size={19}/><select aria-label="Filter service" value={service} onChange={e=>setService(e.target.value)}><option value="">Service</option>{[...new Set(rows.map(r=>String(r.data.service_name || 'Service')))].map(name=><option key={name}>{name}</option>)}</select></label><label className="appointment-filter-select"><Activity size={19}/><select aria-label="Filter status" value={status} onChange={e=>setStatus(e.target.value)}><option value="">Status</option>{['booked','checked_in','in_service','completed','cancelled','no_show'].map(s=><option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}</select></label></div>

    <Dialog open={mobileFilters} onOpenChange={setMobileFilters}><DialogContent className="appointment-mobile-filter-sheet"><DialogTitle>Schedule filters</DialogTitle><DialogDescription>Filter the selected day's appointments.</DialogDescription><label>Customer<input aria-label="Filter customer search" placeholder="Search customer" value={search} onChange={e=>setSearch(e.target.value)}/></label><label>Status<select aria-label="Additional status filter" value={status} onChange={e=>setStatus(e.target.value)}><option value="">All statuses</option>{['booked','checked_in','in_service','completed','cancelled','no_show'].map(s=><option key={s} value={s}>{statusLabel(s)}</option>)}</select></label><Button variant="outline" onClick={()=>{setSearch('');setStatus('');setEmployee('');setAsset('');setService('');}}>Clear filters</Button><Button onClick={()=>setMobileFilters(false)}>Apply filters</Button></DialogContent></Dialog><div className="appointment-reference-views"><div>{([{name:'List',icon:List},{name:'Calendar',icon:CalendarDays},{name:'Gantt',icon:AlignStartVertical}] as const).map(({name,icon:Icon})=><Button key={name} variant={view===name?'default':'ghost'} aria-pressed={view===name} onClick={()=>setView(name)}><Icon size={17}/>{name}</Button>)}</div><div><Button variant={!week?'default':'ghost'} aria-pressed={!week} onClick={()=>setWeek(false)}>Day</Button><Button variant={week?'default':'ghost'} aria-pressed={week} onClick={()=>setWeek(true)}>Week</Button></div></div>

    {view==='Gantt' && !week && <div className="appointment-gantt-scroll"><div className="appointment-reference-gantt" style={{minWidth:Math.max(900,260+(closing-opening)/60*140)}}><div className="appointment-gantt-hours"><span/>{Array.from({length:Math.ceil((closing-opening)/60)},(_,i)=><strong key={i} style={{position:'absolute',left:264+i*140,transform:'translateX(-50%)'}}>{String(Math.floor(opening/60)+i).padStart(2,'0')}:00</strong>)}{showNow&&<i className="appointment-gantt-now-label" style={{left:`calc(260px + (100% - 260px) * ${(nowMinute-opening)/(closing-opening)})`}}>{String(Math.floor(nowMinute/60)).padStart(2,'0')}:{String(nowMinute%60).padStart(2,'0')}</i>}</div>{[false,true].map(physical=><div className="appointment-gantt-group" data-physical={physical} key={String(physical)}><h3>{physical?'PHYSICAL RESOURCES':'EMPLOYEES'}</h3>{resources.filter(r=>r.status==='active' && providers.has(String(r.data.resource_type))!==physical).map(resource=>{const bookings=bookingLanes(visible.filter(r=>(r.data.resource_ids as number[] || []).includes(resource.id)));return <div key={resource.id} className="appointment-gantt-row" style={{minHeight:Math.max(48,...bookings.map(b=>(b.lane+1)*46))}}><div className="appointment-gantt-name"><span className="appointment-avatar">{physical?<PhysicalIcon resource={resource}/>:resource.title.split(' ').slice(0,2).map(w=>w[0]).join('')}</span><strong>{resource.title}</strong></div><div className="appointment-gantt-track" style={{backgroundSize:'140px 100%',backgroundPosition:'54px 0'}}>{showNow&&<i className="appointment-gantt-now" style={{left:`calc(54px + (100% - 54px) * ${(nowMinute-opening)/(closing-opening)})`}}/>}{bookings.map(({item:row,lane})=><button key={row.id} className="appointment-gantt-event" data-status={row.status} style={{left:`calc(54px + (100% - 54px) * ${(minute(String(row.data.starts_at))-opening)/(closing-opening)})`,width:`calc((100% - 54px) * ${Number(row.data.duration_minutes)/(closing-opening)})`,top:lane*46+3}} onClick={()=>onSelect(row.id)}><span><b>{String(row.data.customer_name || row.title)}</b> · {String(row.data.service_name || 'Service')}</span><small><BookingStateIcon status={row.status}/>{statusLabel(row.status)}</small></button>)}</div></div>;})}</div>)}{!resources.length && <p className="p-4 text-sm">No resources configured for this branch.</p>}</div></div>}

    <div hidden={view!=='Calendar' && !(view==='Gantt' && week)}><div className="appointment-timeline-toolbar"><Button variant={!resourceView?'default':'outline'} onClick={()=>setResourceView(false)}><UserRound size={16}/>{term('provider',true)}</Button><Button variant={resourceView?'default':'outline'} onClick={()=>setResourceView(true)}><DoorOpen size={16}/>{term('resource',true)}</Button></div>

    <div className="appointment-timeline-scroll"><div className="appointment-timeline-columns" style={{['--appointment-columns' as string]:Math.max(1,lanes.length),gridTemplateColumns:`76px repeat(${Math.max(1,lanes.length)},minmax(150px,1fr))`}}>



      <div className="appointment-timeline-header"><Clock3 size={17}/>Time</div>{lanes.map(lane=><div key={lane.id} className="appointment-timeline-header"><span className="appointment-avatar">{resourceView?<DoorOpen size={20}/>:lane.title.split(' ').slice(0,2).map(word=>word[0]).join('')}</span><strong>{lane.title}</strong></div>)}



      <div className="appointment-time-axis" style={{height}}>{Array.from({length:Math.ceil((closing-opening)/30)+1},(_,i)=><span key={i} style={{top:i*30*1.25}}>{String(Math.floor((opening+i*30)/60)%12||12)}:{String((opening+i*30)%60).padStart(2,'0')} {(opening+i*30)<720?'AM':'PM'}</span>)}</div>



      {lanes.map(lane=><div key={lane.id} className="appointment-timeline-lane" style={{height}}>{showNow&&<i className="appointment-calendar-now" style={{top:(nowMinute-opening)*1.25}}/>}{onSlot && Array.from({length:Math.ceil((closing-opening)/30)},(_,i)=>opening+i*30).map(minute => {



        const date = week ? String(lane.id) : day;



        const at = candidates(`${date}T${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`,zone);



        const resource = resources.find(r => r.id === Number(lane.id));



        if (at.length !== 1 || at[0] <= Date.now() || visible.some(row => !['cancelled','no_show','completed'].includes(row.status) && (week ? localDay(String(row.data.starts_at),zone)===lane.id : (row.data.resource_ids as number[] || []).includes(Number(lane.id))) && Date.parse(String(row.data.starts_at)) < at[0]+30*60000 && Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000 > at[0])) return null;



        return <button key={`slot-${minute}`} type="button" className="appointment-empty-slot" aria-label={`Prebook ${lane.title} at ${date} ${String(Math.floor(minute/60)).padStart(2,'0')}:${String(minute%60).padStart(2,'0')}`} style={{top:(minute-opening)*1.25,height:37.5}} onClick={()=>onSlot({startsAt:new Date(at[0]).toISOString(),...(resource ? providers.has(String(resource.data.resource_type)) ? {employeeId:Number(resource.data.employee_id)} : {resourceId:resource.id} : {}),key:crypto.randomUUID()})}/>;



      })}{bookingLanes(visible.filter(row=>week?localDay(String(row.data.starts_at),zone)===lane.id:(row.data.resource_ids as number[]||[]).includes(Number(lane.id)))).map(({item:row,lane:column,count})=><button key={row.id} type="button" data-status={row.status} data-compact={Number(row.data.duration_minutes)<45} className="appointment-timeline-booking" title={`${row.data.customer_name || row.title} · ${row.data.service_name} · ${time(String(row.data.starts_at))} · ${row.status}`} aria-label={`${row.data.customer_name || row.title}, ${row.data.service_name}, ${time(String(row.data.starts_at))} to ${time(new Date(Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000).toISOString())}, ${row.status}`} style={{top:(minute(String(row.data.starts_at))-opening)*1.25,height:Math.max(32,Number(row.data.duration_minutes)*1.25-4),left:`calc(${column/count*100}% + 3px)`,width:`calc(${100/count}% - 6px)`,right:"auto"}} onClick={()=>onSelect(row.id)}><strong>{String(row.data.customer_name||row.title)}</strong><span><ServiceIcon name={String(row.data.service_name||'')}/>{String(row.data.service_name||'Service')}</span>{resources.filter(r=>!providers.has(String(r.data.resource_type))&&(row.data.resource_ids as number[]||[]).includes(r.id)).map(r=><span key={r.id}><PhysicalIcon resource={r}/>{r.title}</span>)}<span><CalendarDays size={14}/>{time(String(row.data.starts_at))} – {time(new Date(Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000).toISOString())}</span><small>{statusLabel(row.status)}</small>{showPayments && <AppointmentPaymentStatus id={row.id} revision={row.revision || 1} enabled compact/>}</button>)}</div>)}



      {!lanes.length&&<p className="p-4 text-sm">No configured {resourceView?term('resource',true):term('provider',true)} available in this view.</p>}



    </div></div></div><div className="appointment-timeline-legend"><span><CalendarDays size={15}/>Confirmed</span><span><Clock3 size={15}/>In progress</span><span><CheckCircle2 size={15}/>Completed</span></div>



    <section className="appointment-reference-upcoming" data-view={view}><h2><span className="appointment-desktop-upcoming">Upcoming appointments</span><span className="appointment-mobile-upcoming">Up next</span><button className="appointment-mobile-upcoming" onClick={()=>setView('List')}>View all <ChevronRight size={16}/></button></h2><div className="appointment-mobile-next-list">{visible.filter(row=>!['completed','cancelled','no_show'].includes(row.status)&&Date.parse(String(row.data.starts_at))>=now).sort((a,b)=>Date.parse(String(a.data.starts_at))-Date.parse(String(b.data.starts_at))).slice(0,2).map(row=><button key={row.id} onClick={()=>onSelect(row.id)}><span className="appointment-avatar">{String(row.data.customer_name||row.title).split(' ').slice(0,2).map(w=>w[0]).join('')}</span><time>{time(String(row.data.starts_at))}</time><span><strong>{String(row.data.customer_name||row.title)}</strong><small><ServiceIcon name={String(row.data.service_name||'')}/>{String(row.data.service_name||'Service')}</small></span><span className="appointment-mobile-next-assignment"><small><UserRound size={14}/>{resources.filter(r=>providers.has(String(r.data.resource_type))&&(row.data.resource_ids as number[]||[]).includes(r.id)).map(r=>r.title.split(' ').slice(-2).join(' ')).join(', ')||'—'}</small><small><PhysicalIcon resource={resources.find(r=>!providers.has(String(r.data.resource_type))&&(row.data.resource_ids as number[]||[]).includes(r.id))}/>{resources.filter(r=>!providers.has(String(r.data.resource_type))&&(row.data.resource_ids as number[]||[]).includes(r.id)).map(r=>r.title).join(', ')||'No asset'}</small></span><ChevronRight size={15}/></button>)}</div><div className="appointment-upcoming-scroll"><table><thead><tr>{['Customer','Time','Service','Employee','Resource','Status',''].map((name,i)=><th key={i}>{name}</th>)}</tr></thead><tbody>{(view==='List'?visible:visible.filter(row=>!['completed','cancelled','no_show'].includes(row.status)&&Date.parse(String(row.data.starts_at))>=now)).slice(0,view==='List'?100:4).map(row=><tr key={row.id}><td><button onClick={()=>onSelect(row.id)}><span className="appointment-avatar">{String(row.data.customer_name || row.title).split(' ').slice(0,2).map(w=>w[0]).join('')}</span><b>{String(row.data.customer_name || row.title)}</b></button></td><td><span className="appointment-upcoming-icon"><Clock3 size={16}/>{time(String(row.data.starts_at))} – {time(new Date(Date.parse(String(row.data.starts_at))+Number(row.data.duration_minutes)*60000).toISOString())}</span></td><td><span className="appointment-upcoming-icon"><ServiceIcon name={String(row.data.service_name || '')}/>{String(row.data.service_name || 'Service')}</span></td><td><span className="appointment-upcoming-icon"><UserRound size={18}/>{resources.filter(r=>providers.has(String(r.data.resource_type)) && (row.data.resource_ids as number[] || []).includes(r.id)).map(r=>r.title).join(', ') || '—'}</span></td><td><span className="appointment-upcoming-icon"><PhysicalIcon resource={resources.find(r=>!providers.has(String(r.data.resource_type)) && (row.data.resource_ids as number[] || []).includes(r.id))}/>{resources.filter(r=>!providers.has(String(r.data.resource_type)) && (row.data.resource_ids as number[] || []).includes(r.id)).map(r=>r.title).join(', ') || '—'}</span></td><td><span className="appointment-status-pill" data-status={row.status}><BookingStateIcon status={row.status}/>{statusLabel(row.status)}</span></td><td><button aria-label={`View appointment ${row.id}`} onClick={()=>onSelect(row.id)}>•••</button></td></tr>)}</tbody></table>{!visible.length && <p className="p-4 text-sm">No appointments match the selected date and filters.</p>}</div><footer>{visible.length ? `1 – ${Math.min(visible.length,view==='List'?100:4)} of ${visible.length}` : '0 appointments'}<small>{zone}</small></footer></section>

  </section>;



}
