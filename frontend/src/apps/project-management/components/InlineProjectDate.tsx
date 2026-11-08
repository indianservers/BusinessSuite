import { CalendarDays } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/** Shows a readable date; commits edits only when the date field is left. */
export default function InlineProjectDate({ label, value, disabled, overdue, onSave }: {
  label: string; value?: string; disabled: boolean; overdue: boolean;
  onSave: (value: string | null) => Promise<boolean>;
}) {
  const original = value?.slice(0,10) || "";
  const [draft, setDraft] = useState(original), [editing, setEditing] = useState(false);
  const cancelled = useRef(false);
  useEffect(() => setDraft(original), [original]);
  const date = original ? new Date(`${original}T12:00:00`) : null;
  const valid = date && !Number.isNaN(date.getTime());
  if (!editing) return <button type="button" className={`inline-project-date ${overdue ? "is-overdue" : ""}`} disabled={disabled}
    aria-label={`Edit ${label}`} title={valid ? `${label}: ${date.toLocaleDateString()}` : `${label}: Not scheduled`}
    onClick={() => {cancelled.current=false;setDraft(original);setEditing(true);}}>
    {valid ? <span>{date.toLocaleDateString(undefined,{day:"numeric",month:"short",year:"2-digit"})}</span> : <CalendarDays size={14} aria-hidden="true"/>}
    {!valid && <span className="sr-only">Not scheduled</span>}
  </button>;
  return <input autoFocus aria-label={label} type="date" className={overdue ? "is-overdue" : ""} disabled={disabled} value={draft}
    onChange={e=>setDraft(e.target.value)}
    onBlur={e=>{
      const next=e.currentTarget.value;
      if (cancelled.current || next===original) {setDraft(original);setEditing(false);return;}
      void onSave(next || null).then(saved=>{if(!saved)setDraft(original);setEditing(false);});
    }}
    onKeyDown={e=>{
      if(e.key==="Enter")e.currentTarget.blur();
      if(e.key==="Escape"){e.preventDefault();e.stopPropagation();cancelled.current=true;setDraft(original);setEditing(false);}
    }}/>
}
