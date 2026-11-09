import { useState } from "react";
import { useLocation } from "react-router-dom";
import { ArrowUpRight, ChevronDown, Plus } from "lucide-react";
import { MobileSheet } from "./MobilePrimitives";
import type { NewAction } from "@/components/app/NewMenu";

export default function MobileCreateMenu({ actions, disabled }: { actions: NewAction[]; disabled?: boolean }) {
  const [open, setOpen] = useState(false), [all, setAll] = useState(false);
  const { pathname } = useLocation();
  const ranked = [...actions].sort((a, b) => Number(!!b.menuPaths?.some(path => pathname === path || pathname.startsWith(path + "/"))) - Number(!!a.menuPaths?.some(path => pathname === path || pathname.startsWith(path + "/"))));
  if (!actions.length) return null;
  return <>
    <button type="button" className="mobile-module-add" data-state={open ? "open" : "closed"} aria-label="Add new record" aria-haspopup="dialog" aria-expanded={open} disabled={disabled} onClick={() => { setAll(false); setOpen(true); }}><Plus size={26} aria-hidden="true" /></button>
    <MobileSheet navigation title="Create something new" open={open} onClose={() => setOpen(false)}>
      <p className="text-sm text-muted-foreground">Quick actions for your current module</p>
      <div className="mobile-create-list">{(all ? ranked : ranked.slice(0, 6)).map(action => <button type="button" key={action.label} disabled={action.disabled} onClick={() => { setOpen(false); requestAnimationFrame(action.onSelect); }}>
        <span className="mobile-create-icon"><action.icon size={21} aria-hidden="true" /></span><span><strong>{action.label}</strong><small>{action.description}</small></span><ArrowUpRight size={16} aria-hidden="true" />
      </button>)}</div>
      {ranked.length > 6 && <button type="button" className="mobile-filter-trigger justify-center" aria-expanded={all} onClick={() => setAll(value => !value)}><ChevronDown size={16} aria-hidden="true" />{all ? "Show fewer actions" : `View all ${ranked.length} actions`}</button>}
    </MobileSheet>
  </>;
}
