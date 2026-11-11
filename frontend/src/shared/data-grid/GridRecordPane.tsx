import { useAuthStore } from "@/store/authStore";
import { useLocation } from "react-router-dom";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Maximize2, X } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useMobile } from "@/components/mobile/useMobile";

export default function GridRecordPane({ title, children, close, expand, managedFocusReturn, className = "", contentClassName = "" }: { title: string; children: ReactNode; close: () => void; expand?: () => void; managedFocusReturn?: boolean; className?: string; contentClassName?: string }) {
  const mobile = useMobile();
  const user = useAuthStore(s=>s.user), location = useLocation();
  const widthKey = `record-pane-width:${user?.access?.companyId}:${user?.id}:${location.pathname}`;
  const [width,setWidth] = useState(()=>{try{return Math.max(280,Math.min(800,Number(localStorage.getItem(widthKey))||340));}catch{return 340;}});
  const [resizing,setResizing] = useState(false);
  useEffect(()=>{try{localStorage.setItem(widthKey,String(width));}catch{}},[width,widthKey]);
  useEffect(()=>{if(!resizing)return;const move=(event:PointerEvent)=>setWidth(Math.max(280,Math.min(800,window.innerWidth-event.clientX-24)));const end=()=>setResizing(false);window.addEventListener("pointermove",move);window.addEventListener("pointerup",end);return()=>{window.removeEventListener("pointermove",move);window.removeEventListener("pointerup",end);};},[resizing]);
  const heading = useRef<HTMLHeadingElement>(null);
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    if (mobile) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    heading.current?.focus();
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !document.querySelector('[role="dialog"]')) { event.stopPropagation(); closeRef.current(); }
    };
    window.addEventListener("keydown", escape);
    return () => { window.removeEventListener("keydown", escape); if (!managedFocusReturn && opener?.isConnected) opener.focus(); };
  }, [mobile]);
  if (mobile) return <Dialog open onOpenChange={open => { if (!open) close(); }}><DialogContent className="udg-details-dialog" onCloseAutoFocus={event=>{if(managedFocusReturn)event.preventDefault();}}><DialogTitle>{title}</DialogTitle>{expand && <button type="button" className="inline-flex min-h-11 items-center gap-2 rounded-md border px-3 py-2 text-sm" onClick={expand}><Maximize2 size={16} aria-hidden="true"/>Open full record</button>}{children}</DialogContent></Dialog>;
  return <aside className={`udg-details ${className}`} aria-label={`Record details: ${title}`} style={{flexBasis:width}}>
    <div role="separator" tabIndex={0} aria-label="Resize record preview" aria-orientation="vertical" aria-valuemin={280} aria-valuemax={800} aria-valuenow={width} className="udg-pane-resizer" onPointerDown={e=>{e.preventDefault();setResizing(true);}} onKeyDown={e=>{if(e.key==="ArrowLeft"||e.key==="ArrowRight"){e.preventDefault();setWidth(w=>Math.max(280,Math.min(800,w+(e.key==="ArrowLeft"?40:-40))));}}}/>
    <header><div><small>Record details</small><h2 ref={heading} tabIndex={-1}>{title}</h2></div>
      {expand && <button type="button" aria-label="Open full record" title="Open full record" onClick={expand}><Maximize2 size={16}/></button>}
      <button type="button" aria-label="Close record details" onClick={close}><X size={18}/></button>
    </header><div className={`udg-details-body ${contentClassName}`}>{children}</div>
  </aside>;
}
