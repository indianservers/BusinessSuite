import { useState, useEffect, useId, useRef, type ReactNode } from 'react';
/** Keep fields mounted while a completed section is summarized. */
export default function PrebookingSection({title,summary,complete,children,field,blockingError}:{title:string;summary?:string;complete?:boolean;children:ReactNode;field?:string;blockingError?:string}) {
  const [open,setOpen]=useState(true),id=useId();
  const previousError=useRef('');
  useEffect(()=>{if(blockingError && blockingError!==previousError.current)setOpen(true);if(blockingError)previousError.current=blockingError;else if(complete)previousError.current='';},[blockingError,complete]);
  return <section className="prebooking-section" aria-label={`${title} section`} data-booking-section={field}>
    <div className="prebooking-section-heading"><h3>{title} {blockingError && <span className="prebooking-warning-badge">Needs review</span>}</h3>{(complete || !open) && <button type="button" aria-expanded={open} aria-controls={id} onClick={()=>setOpen(v=>!v)}>{open?'Collapse':'Edit'} {title.toLowerCase()}</button>}</div>
    {!open && <p className="prebooking-section-summary">{summary || (complete?'Completed':'Needs review')}</p>}
    <div id={id} hidden={!open} data-section-body>{children}</div>
  </section>;
}
export function focusBookingField(root:HTMLElement|null,selector:string){
  const field=root?.querySelector<HTMLElement>(selector);if(!field)return;
  const section=field.closest('[data-booking-section]');
  if(section?.querySelector('[data-section-body][hidden]'))section.querySelector<HTMLButtonElement>('.prebooking-section-heading button')?.click();
  let parent=field.parentElement;while(parent&&parent!==root){if(parent instanceof HTMLDetailsElement)parent.open=true;parent=parent.parentElement;}
  requestAnimationFrame(()=>{field.focus();field.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
}
