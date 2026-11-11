import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Plus, Search, type LucideIcon } from "lucide-react";
import { useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { createDescriptions, createGroup, createPriority } from "./create-menu-model";
import "./new-menu.css";
import MobileCreateMenu from "@/components/mobile/MobileCreateMenu";

export type NewAction = { label: string; description: string; icon: LucideIcon; onSelect: () => void; disabled?: boolean; menuPaths?: string[]; group?: string; keywords?: string };
export default function NewMenu({ actions, disabled, floating = false }: { actions: NewAction[]; disabled?: boolean; floating?: boolean }) {
  const [open, setOpen] = useState(false);
  const selecting = useRef(false);
  const [query, setQuery] = useState("");
  const searchInput = useRef<HTMLInputElement>(null);
  useEffect(() => { if (!open) return; const frame = requestAnimationFrame(() => searchInput.current?.focus()); return () => cancelAnimationFrame(frame); }, [open]);
  const location = useLocation(), user = useAuthStore(s => s.user);
  const module = location.pathname.split("/")[1];
  const prepared = actions.map(action => ({ ...action, group: action.group || createGroup(action.label, module), description: module === "crm" ? createDescriptions[action.label] || action.description : action.description })).sort((a, b) => createPriority(a.label, module, user?.role === "employee") - createPriority(b.label, module, user?.role === "employee"));
  const filtered = prepared.filter(action => `${action.label} ${action.description} ${action.group} ${action.keywords || ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  const groups = [...new Set(filtered.map(action => action.group))];
  if (floating) return <MobileCreateMenu actions={prepared} disabled={disabled} />;
  if (!actions.length) return null;
  return <Dropdown.Root modal={false} open={open} onOpenChange={value => { setOpen(value); if (value) setQuery(""); }}><Dropdown.Trigger className="suite-new-trigger" disabled={disabled}><Plus size={16} aria-hidden="true" />Create<ChevronDown size={14} /></Dropdown.Trigger><Dropdown.Portal><Dropdown.Content onCloseAutoFocus={event => { if (selecting.current) event.preventDefault(); selecting.current = false; }} onEscapeKeyDown={() => setOpen(false)} className="suite-new-menu" align="end" side="bottom" sideOffset={8} collisionPadding={12}>
    <div className="suite-create-search"><Search size={16} aria-hidden="true"/><input ref={searchInput} aria-label="Search create actions" placeholder="Search actions…" value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => { if (event.key !== "Escape" && event.key !== "Tab") event.stopPropagation(); if (event.key === "ArrowDown") { event.preventDefault(); event.currentTarget.closest('[role="menu"]')?.querySelector<HTMLElement>('[role="menuitem"]:not([data-disabled])')?.focus(); } }}/></div>
    {!filtered.length && <p className="suite-create-empty" role="status">No matching actions. Try task, leave, or document.</p>}
    {groups.map(group => <Dropdown.Group key={group}><Dropdown.Label className="suite-create-group">{group}</Dropdown.Label>{filtered.filter(action => action.group === group).map(action => <Dropdown.Item key={action.label} disabled={action.disabled} onSelect={() => {
    // Finish dismissing the menu before mounting a dialog with its own focus scope.
    selecting.current = true;
    setOpen(false);
    requestAnimationFrame(() => action.onSelect());
  }}><action.icon size={18} /><span className="suite-new-item-copy">{action.label}<small>{action.description}</small></span><Plus size={13} /></Dropdown.Item>)}</Dropdown.Group>)}
    </Dropdown.Content></Dropdown.Portal></Dropdown.Root>;
}
