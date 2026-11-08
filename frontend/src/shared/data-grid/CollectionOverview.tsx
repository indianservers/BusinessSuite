import { useState } from "react";
import { CalendarDays, GanttChart, Layers, ZoomIn, ZoomOut } from "lucide-react";
import { DAY, scheduleRecords, statusCounts, type CollectionField } from "./collection-model";
import { groupAppearance } from "./GroupLabel";
import "./collection-overview.css";
const dateLabel = (day: number) => new Date(day).toLocaleDateString("en-IN", {day:"2-digit",month:"short",year:"numeric",timeZone:"UTC"});
export default function CollectionOverview<T>({rows,fields,total,onOpen}:{rows:T[];fields:CollectionField<T>[];total?:number;onOpen?:(row:T)=>void}) {
  const [open,setOpen] = useState(false), [zoom,setZoom] = useState(1);
  const counts = statusCounts(rows,fields), schedule = scheduleRecords(rows,fields);
  const first = schedule.length ? Math.min(...schedule.map(r=>r.start)) : 0;
  const last = schedule.length ? Math.max(...schedule.map(r=>r.end)) : first;
  const days = (last-first)/DAY+1, tickCount=Math.min(6,Math.max(1,Math.ceil((last-first)/DAY+1))), width = Math.max(600,Math.min(4000,days*12))*zoom;
  return <div className="suite-collection-overview">
    <div className="suite-collection-counts" aria-label="Collection summary counts">
      <div className="suite-count-total"><span className="suite-count-icon"><Layers size={15} aria-hidden="true"/></span><span>Loaded records<strong>{rows.length.toLocaleString()}</strong></span></div>
      {total!==undefined && <div><span>Matching records<strong>{total.toLocaleString()}</strong></span></div>}
      {counts.map(({title,count})=>{const {Icon,tone}=groupAppearance(title,"Status");return <div key={title} className={`suite-count-${tone}`}><span className="suite-count-icon"><Icon size={15} aria-hidden="true"/></span><span>{title}<strong>{count.toLocaleString()}</strong></span></div>;})}
    </div>
    {schedule.length>0 && <section className="suite-collection-schedule" aria-label="Record schedule">
      <button type="button" className="suite-gantt-toggle" aria-expanded={open} onClick={()=>setOpen(value=>!value)}><GanttChart size={14} aria-hidden="true"/>Gantt<span>{schedule.length} scheduled / {rows.length} loaded</span></button>
      {open && <><header><span><CalendarDays size={14} aria-hidden="true"/>{dateLabel(first)} – {dateLabel(last)}</span><div><button type="button" aria-label="Zoom out schedule" disabled={zoom<=.5} onClick={()=>setZoom(value=>Math.max(.5,value-.5))}><ZoomOut size={15}/></button><span>{Math.round(zoom*100)}%</span><button type="button" aria-label="Zoom in schedule" disabled={zoom>=3} onClick={()=>setZoom(value=>Math.min(3,value+.5))}><ZoomIn size={15}/></button></div></header>
      <p>Read-only schedule · loaded records with valid start and end dates. Open the record to change dates.</p>
      <div className="suite-gantt-scroll"><div style={{minWidth:width+200}}><div className="suite-gantt-axis"><span>Record</span><div style={{width}}>{Array.from({length:tickCount},(_,i)=>{const day=first+Math.round((days-1)*i/Math.max(1,tickCount-1))*DAY;return <time key={i} style={{left:`${i/Math.max(1,tickCount-1)*100}%`}} dateTime={new Date(day).toISOString().slice(0,10)}>{dateLabel(day)}</time>;})}</div></div>
      {schedule.map((record,index)=><div className="suite-gantt-row" key={index}><div className="suite-gantt-label">{onOpen?<button type="button" onClick={()=>onOpen(record.row)} title={record.title}>{record.title}</button>:<span title={record.title}>{record.title}</span>}</div><div className="suite-gantt-track" style={{width}}><span className="suite-gantt-bar" style={{left:`${(record.start-first)/DAY/days*100}%`,width:`${(record.end-record.start+DAY)/DAY/days*100}%`}} title={`${record.title}: ${dateLabel(record.start)} – ${dateLabel(record.end)}${record.progress!==undefined?` · ${record.progress}% complete`:""}`}><span style={{width:`${record.progress??0}%`}}/>{record.progress!==undefined&&<small>{record.progress}%</small>}</span></div></div>)}</div></div></>}
    </section>}
  </div>;
}
