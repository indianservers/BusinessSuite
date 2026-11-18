import { useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import type { LensRecord } from "./RecordLensViews";
import { dayNumber, formatDay, todayNumber } from "./schedule";

const dateKey = (date: Date) => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
export default function CalendarLens({records,onOpen}:{records:LensRecord[];onOpen:(record:LensRecord)=>void}) {
  const [cursor,setCursor] = useState(() => new Date(new Date().getFullYear(),new Date().getMonth(),1));
  const [agenda,setAgenda] = useState(false);
  const first = new Date(cursor); first.setDate(1-first.getDay());
  const dates = Array.from({length:42},(_,index)=>{const date=new Date(first);date.setDate(date.getDate()+index);return date;});
  const unscheduled = records.filter(record=>dayNumber(record.due)===null);
  const inMonth = records.filter(record=>record.due?.slice(0,7)===dateKey(cursor).slice(0,7) && dayNumber(record.due)!==null).sort((a,b)=>a.due!.localeCompare(b.due!));
  return <section className="rl-calendar" aria-label="Workspace calendar">
    <header className="rl-toolbar"><div><button aria-label="Previous month" onClick={()=>setCursor(new Date(cursor.getFullYear(),cursor.getMonth()-1,1))}><ChevronLeft size={16}/></button><button onClick={()=>setCursor(new Date(new Date().getFullYear(),new Date().getMonth(),1))}>Today</button><button aria-label="Next month" onClick={()=>setCursor(new Date(cursor.getFullYear(),cursor.getMonth()+1,1))}><ChevronRight size={16}/></button></div><h3 aria-live="polite">{cursor.toLocaleDateString(undefined,{month:"long",year:"numeric"})}</h3><div><button aria-pressed={!agenda} onClick={()=>setAgenda(false)}>Month</button><button aria-pressed={agenda} onClick={()=>setAgenda(true)}>Agenda</button></div></header>
    {agenda ? <div className="rl-agenda">{inMonth.length ? inMonth.map(record=><button key={record.id} onClick={()=>onOpen(record)}><time>{formatDay(dayNumber(record.due)!,{weekday:"short",month:"short",day:"numeric"})}</time><i style={{background:record.color || "#8661d6"}}/><span><strong>{record.title}</strong><small>{record.owner || "Unassigned"} · {record.status}</small></span></button>) : <div className="rl-empty"><CalendarDays size={24}/><h3>No dates this month</h3><p>Choose another month or open an unscheduled record below.</p></div>}</div> : <>
      <div className="rl-calendar-week">{["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map(day=><span key={day}>{day}</span>)}</div><div className="rl-calendar-grid">{dates.map(date=><div key={dateKey(date)} className={`${date.getMonth()!==cursor.getMonth()?"outside":""} ${dayNumber(dateKey(date))===todayNumber()?"today":""}`}><time dateTime={dateKey(date)}>{date.getDate()}</time>{records.filter(record=>record.due?.slice(0,10)===dateKey(date)).map(record=><button key={record.id} style={{borderLeftColor:record.color || "#8661d6"}} onClick={()=>onOpen(record)} title={`${record.title} · ${record.status}`}>{record.title}</button>)}</div>)}</div>
    </>}
    {unscheduled.length>0 && <details className="rl-calendar-unscheduled"><summary>{unscheduled.length} unscheduled records <span>Open a record to add dates</span></summary><div>{unscheduled.map(record=><button key={record.id} onClick={()=>onOpen(record)}><strong>{record.title}</strong><span>{record.owner || record.status}</span></button>)}</div></details>}
    <p className="rl-scope">{inMonth.length} records dated this month · {unscheduled.length} unscheduled · Workspace filters stay applied.</p>
  </section>;
}
