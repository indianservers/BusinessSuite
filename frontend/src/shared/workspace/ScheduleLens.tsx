import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, Crosshair, Minus, Plus } from "lucide-react";
import type { LensRecord } from "./RecordLensViews";
import { formatDay, scheduleBar, scheduleRange, todayNumber } from "./schedule";
import "./record-lenses.css";

type Props = {view: string; records: LensRecord[]; onOpen: (record: LensRecord) => void};
const colours = ["#8661d6", "#159d8c", "#528bd2", "#cb9138", "#c36596"];

/** One timeline for portfolio, task and opportunity records; editing remains in their own detail UI. */
export default function ScheduleLens({view, records, onOpen}: Props) {
  const scroll = useRef<HTMLDivElement>(null);
  const [viewport, setViewport] = useState(900);
  const [zoom, setZoom] = useState<number | null>(null);
  const [group, setGroup] = useState("none");
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const {start, days} = useMemo(() => scheduleRange(records), [records]);
  useEffect(() => {
    const element = scroll.current;
    if (!element) return;
    const observer = new ResizeObserver(() => setViewport(element.clientWidth));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const labelWidth = Math.min(260, Math.max(160, viewport * .3));
  const fitScale = Math.max(.01, (viewport - labelWidth) / days);
  const scale = zoom ?? fitScale;
  const width = Math.max(viewport - labelWidth, days * scale);
  const step = Math.max(1, Math.ceil(86 / scale));
  const today = todayNumber(), todayX = (today - start + .5) * scale;
  const scheduled = records.filter(record => scheduleBar(record, start));
  const groups = group === "none" ? [""] : [...new Set(records.map(record => group === "owner" ? record.owner || "Unassigned" : record.status || "Unassigned"))];
  const months: {day: number; length: number; label: string}[] = [];
  for (let day = 0; day < days;) {
    const date = new Date((start + day) * 86400000);
    const next = Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 1) / 86400000;
    const length = Math.min(days - day, next - start - day);
    months.push({day, length, label: formatDay(start + day, {month:"long", year:"numeric"})});
    day += length;
  }
  function focusToday() {
    if (scroll.current) scroll.current.scrollTo({left: Math.max(0, todayX - (viewport - labelWidth) / 2), behavior:"smooth"});
  }
  return <section className="rl-gantt rl-schedule" aria-label={`${view} schedule`}>
    <header className="rl-toolbar">
      <span><CalendarDays size={15}/><strong>{scheduled.length}</strong> scheduled · {records.length - scheduled.length} unscheduled</span>
      <div className="rl-schedule-tools">
        <label>Group <select aria-label="Schedule grouping" value={group} onChange={event => {setGroup(event.target.value); setCollapsed([]);}}><option value="none">None</option><option value="status">Status</option><option value="owner">Owner</option></select></label>
        <button disabled={today < start || today >= start + days} title="Scroll to the current day" onClick={focusToday}><Crosshair size={13}/>Today</button>
        <button aria-label="Zoom out schedule" disabled={scale <= fitScale / 2} onClick={() => setZoom(Math.max(fitScale / 2, scale / 1.5))}><Minus size={14}/></button>
        <button aria-pressed={zoom === null} onClick={() => {setZoom(null); scroll.current?.scrollTo({left:0});}}>Fit</button>
        <button aria-label="Zoom in schedule" disabled={scale >= 56} onClick={() => setZoom(Math.min(56, scale * 1.5))}><Plus size={14}/></button>
      </div>
    </header>
    <div className="rl-gantt-scroll" ref={scroll} tabIndex={0} aria-label="Scrollable schedule" style={{"--schedule-label-width":`${labelWidth}px`} as React.CSSProperties}>
      <div style={{width:width + labelWidth}}>
        <div className="rl-gantt-axis rl-schedule-axis"><strong>Work & milestones<small>{records.length} records in this result</small></strong><div style={{width}}>
          <div className="rl-schedule-months">{months.map(month => <span key={month.day} style={{left:month.day * scale, width:month.length * scale}}>{month.label}</span>)}</div>
          {Array.from({length:Math.ceil(days / step)}, (_, index) => <time key={index} style={{left:index * step * scale}}>{formatDay(start + index * step)}</time>)}
          {todayX >= 0 && todayX < width && <span className="rl-today-label" style={{left:todayX}}>Today</span>}
        </div></div>
        {groups.map(name => <div key={name}>
          {group !== "none" && <button className="rl-schedule-group" aria-expanded={!collapsed.includes(name)} onClick={() => setCollapsed(current => current.includes(name) ? current.filter(value => value !== name) : [...current, name])}><span>{collapsed.includes(name) ? "▸" : "▾"} {name}</span><small>{records.filter(record => (group === "owner" ? record.owner || "Unassigned" : record.status || "Unassigned") === name).length} records</small></button>}
          {!collapsed.includes(name) && records.filter(record => group === "none" || (group === "owner" ? record.owner || "Unassigned" : record.status || "Unassigned") === name).map((record, index) => {
            const bar = scheduleBar(record, start);
            return <div className="rl-gantt-row" key={record.id}><button title={record.title} onClick={() => onOpen(record)}><strong>{record.title}</strong><span>{record.owner || record.status}</span></button><div style={{width, backgroundSize:`${step * scale}px 100%`}}>
              {todayX >= 0 && todayX < width && <i className="rl-today-line" aria-hidden="true" style={{left:todayX}}/>}
              {bar ? <button className={`rl-gantt-bar ${bar.reversed ? "rl-date-conflict" : ""}`} style={{left:bar.offset * scale, width:Math.max(4, bar.days * scale), background:record.color || colours[index % colours.length]}} onClick={() => onOpen(record)} aria-label={`Open ${record.title}, ${formatDay(start + bar.offset)} to ${formatDay(start + bar.offset + bar.days - 1)}${bar.reversed ? ", check reversed dates" : ""}`} title={`${record.title} · ${record.start || record.due} → ${record.due || record.start}${bar.reversed ? " · Check reversed dates" : ""}`}><span>{view === "timeline" ? record.title : record.status}</span>{record.progress !== undefined && <i style={{width:`${Math.max(0, Math.min(100, record.progress))}%`}}/>}</button> : <button className="rl-schedule-undated" onClick={() => onOpen(record)}>Set dates →</button>}
            </div></div>;
          })}
        </div>)}
      </div>
    </div>
    <p className="rl-scope">{formatDay(start, {month:"short", day:"numeric", year:"numeric"})} – {formatDay(start + days - 1, {month:"short", day:"numeric", year:"numeric"})} · Open a record to edit its dates. Your workspace filters stay applied.</p>
  </section>;
}
