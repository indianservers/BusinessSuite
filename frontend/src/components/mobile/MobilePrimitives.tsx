import { WhatsAppIcon } from "@/components/actions/BrandIcons";
import { useEffect, useRef, useState, type ReactNode, type SyntheticEvent } from "react";
import { Filter, Mail, Phone, StickyNote } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useMobile } from "./useMobile";
import "./mobile-experience.css";

export function MobileSheet({ open, onClose, title, children, navigation = false, fallbackFocus, onClosed }: { open: boolean; onClose: () => void; title: string; children: ReactNode; navigation?: boolean; fallbackFocus?: HTMLElement | null; onClosed?: () => void }) {
  const start = useRef<number | null>(null);
  const opener = useRef<HTMLElement | null>(null);
  const mobile=useMobile();
  if(!mobile)return null;
  return <Dialog open={open} onOpenChange={value => { if (!value) onClose(); }}><DialogContent data-navigation-sheet={navigation || undefined} className="mobile-experience-sheet" onOpenAutoFocus={() => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }} onCloseAutoFocus={event => {
    const target=opener.current?.isConnected ? opener.current : fallbackFocus;
    if (target?.isConnected) { event.preventDefault(); target.focus(); }
    onClosed?.();
  }}><button type="button" className="mobile-sheet-handle" aria-label="Drag down or tap to close" onClick={onClose} onPointerDown={event => { start.current = event.clientY; event.currentTarget.setPointerCapture(event.pointerId); }} onPointerUp={event => { if (start.current !== null && event.clientY - start.current > 65) onClose(); start.current = null; }}><span /></button><DialogTitle className="text-xl font-semibold pr-7">{title}</DialogTitle>{children}</DialogContent></Dialog>;
}
export function MobileFilters({ children, chips = [], onClear, label = "Filters" }: { children: ReactNode; chips?: string[]; onClear?: () => void; label?: string }) {
  const mobile = useMobile(); const [open, setOpen] = useState(false);
  useEffect(()=>{if(!mobile)setOpen(false);},[mobile]);
  if (!mobile) return <>{children}</>;
  return <div className="mobile-filter-control"><button type="button" className="mobile-filter-trigger" aria-label={label} title={chips.length ? `${chips.length} active filters` : label} onClick={() => setOpen(true)}><Filter size={16}/>{label}{chips.length > 0 && <b>{chips.length}</b>}</button><div className="mobile-filter-chips">{chips.map(chip => <span key={chip}>{chip}</span>)}{chips.length > 0 && onClear && <button type="button" onClick={onClear}>Clear</button>}</div><MobileSheet open={open} onClose={() => setOpen(false)} title={label}><div className="mobile-filter-fields">{children}</div><button type="button" className="mobile-primary-action" onClick={() => setOpen(false)}>Show results</button></MobileSheet></div>;
}
export function MobileContactActions({ phone, email, onNote }: { phone?: string | null; email?: string | null; onNote?: () => void }) {
  const mobile = useMobile(); if (!mobile || (!phone && !email && !onNote)) return null;
  const clean = phone?.replace(/[^\d+]/g, ""); const digits = clean?.replace(/\D/g, "");
  return <nav className="mobile-contact-strip" aria-label="Contact actions">{clean && <a aria-label="Call contact" data-action-tooltip="Call this contact" href={`tel:${clean}`}><Phone className="text-teal-600" size={18}/>Call</a>}{digits && <a aria-label="Send WhatsApp message" data-action-tooltip="Send WhatsApp message" href={`https://wa.me/${digits}`} target="_blank" rel="noreferrer"><WhatsAppIcon className="h-[18px] w-[18px] text-[#25D366]"/>WhatsApp</a>}{email && <a aria-label="Compose email to this contact" data-action-tooltip="Compose email to this contact" href={`mailto:${email}`}><Mail className="text-blue-600" size={18}/>Email</a>}{onNote && <button type="button" onClick={onNote}><StickyNote size={18}/>Add note</button>}</nav>;
}
export function MobileDisclosure({ title, children, maxWidth = 767, keepMounted = false, className = "", initiallyOpen }: { title: string; children: ReactNode; maxWidth?: number; keepMounted?: boolean; className?: string; initiallyOpen?: boolean }) {
  const mobile = useMobile(maxWidth);
  const [expanded,setExpanded] = useState(initiallyOpen ?? false);
  const detailsRef = useRef<HTMLDetailsElement>(null);
  // Native validation must be able to focus required controls inside disclosure.
  const revealInvalid = () => {
    if (detailsRef.current) detailsRef.current.open = true;
  };
  useEffect(() => {
    const details = detailsRef.current;
    if (!mobile || !details) return;
    const revealServerErrors = () => {
      if (details.querySelector('[aria-invalid="true"], [role="alert"]')) details.open = true;
    };
    revealServerErrors();
    const observer = new MutationObserver(revealServerErrors);
    observer.observe(details, {subtree:true, childList:true, attributes:true, attributeFilter:["aria-invalid", "role"]});
    return () => observer.disconnect();
  }, [mobile]);
  if(keepMounted)return <details ref={detailsRef} className={`${mobile ? "mobile-disclosure" : ""} ${className}`} open={!mobile || expanded} onToggle={event => {if(mobile)setExpanded(event.currentTarget.open);}} onInvalidCapture={revealInvalid}><summary style={!mobile ? {display:"none"} : undefined}>{title}</summary><div style={!mobile ? {display:"contents"} : undefined}>{children}</div></details>;
  return mobile ? <details ref={detailsRef} {...(initiallyOpen === undefined ? {} : {open:expanded,onToggle:(event:SyntheticEvent<HTMLDetailsElement>)=>setExpanded(event.currentTarget.open)})} className={`mobile-disclosure ${className}`} onInvalidCapture={revealInvalid}><summary>{title}</summary><div>{children}</div></details> : <>{children}</>;
}
export function MobileSteps({ steps, current, onChange }: { steps: string[]; current: number; onChange: (index: number) => void }) {
  return <nav className="mobile-stepper" aria-label="Progress">{steps.map((label, index) => <button type="button" key={label} aria-current={index === current ? "step" : undefined} onClick={() => onChange(index)}><span>{index + 1}</span>{label}</button>)}</nav>;
}
