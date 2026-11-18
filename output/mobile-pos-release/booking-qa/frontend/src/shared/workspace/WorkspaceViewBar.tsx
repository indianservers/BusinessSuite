import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as Popover from "@radix-ui/react-popover";
import { Activity, BarChart3, CalendarDays, Check, Columns3, FileText, Files, FormInput, GalleryHorizontal, Ellipsis, GitBranch, LayoutDashboard, List, Map, MessageSquare, Network, PanelTop, Plus, Search, Star, Table2, Users, X, type LucideIcon } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import "./workspace-views.css";
import { useRecordViewHost } from "@/shared/data-grid/RecordViewHost";

export const viewIcons: Record<string, LucideIcon> = { list: List, table: Table2, board: Columns3, gallery: GalleryHorizontal, gantt: GitBranch, timeline: Activity, calendar: CalendarDays, dashboard: LayoutDashboard, workload: BarChart3, team: Users, activity: Activity, channel: MessageSquare, docs: FileText, files: Files, form: FormInput, mindmap: Network, whiteboard: PanelTop, map: Map };
export type WorkspaceView = { id: string; label: string; description: string; icon?: keyof typeof viewIcons; category?: "Work" | "Plan" | "Collaborate" | "Explore"; href?: string; color?: string };

/** Presentation preferences only. All records, permissions and mutations stay with the owning workspace. */
export default function WorkspaceViewBar({ scope, active, views, onChange, primary, label = "Workspace views" }: { scope: string; active: string; views: WorkspaceView[]; onChange: (id: string) => void; primary?: string[]; label?: string }) {
  const user = useAuthStore(state => state.user);
  const recordHost=useRecordViewHost();
  const recordAliases=["table","grid","list","compact","gallery","cards","profile"];
  const redundant=(view:WorkspaceView)=>!!recordHost?.registration&&recordAliases.includes(active)&&recordAliases.includes(view.id)&&(recordHost.registration.table||view.id!=="table");
  const key = `suite:workspace-views:v1:${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-branch") || ""}:${scope}`;
  const initialKey = JSON.stringify(primary || views.slice(0, 6).map(view => view.id));
  const initial = useMemo<string[]>(() => JSON.parse(initialKey), [initialKey]);
  const [pinned, setPinned] = useState<string[]>(initial);
  const [ready, setReady] = useState("");
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  useEffect(() => { try { const saved = JSON.parse(localStorage.getItem(key) || "null"); setPinned(Array.isArray(saved) && saved.every(id => typeof id === "string") ? [...new Set<string>(saved)] : initial); } catch { setPinned(initial); } setReady(key); }, [key, initial]);
  useEffect(() => { if (ready === key) { try { localStorage.setItem(key, JSON.stringify(pinned)); } catch { /* Navigation remains available when storage is unavailable. */ } } }, [key, ready, pinned]);
  const available = views.filter(view => `${view.label} ${view.description} ${view.category || "Work"}`.toLowerCase().includes(search.trim().toLowerCase()));
  const visible = views.filter(view => !redundant(view)&&(pinned.includes(view.id) || view.id === active));
  function choose(view: WorkspaceView) { if (!pinned.includes(view.id)) setPinned(current => [...current, view.id]); setOpen(false); setSearch(""); if (!view.href) onChange(view.id); }
  const icon = (view: WorkspaceView, size = 15) => { const Icon = viewIcons[view.icon || view.id] || PanelTop; return <Icon size={size} aria-hidden="true"/>; };
  return <div className={`wv-bar ${recordHost?"wv-unified-records":""}`}>
    {recordHost&&<div className="wv-record-slot" ref={recordHost.setHost}/>}
    <nav className="wv-tabs" aria-label={label}>{visible.map(view => view.href ? <Link key={view.id} to={view.href} className={`wv-tab ${active === view.id ? "active" : ""}`} aria-current={active === view.id ? "page" : undefined}>{icon(view)}<span>{view.label}</span></Link> : <button type="button" key={view.id} className={`wv-tab ${active === view.id ? "active" : ""}`} aria-pressed={active === view.id} onClick={() => onChange(view.id)}>{icon(view)}<span>{view.label}</span></button>)}</nav>
    <Popover.Root open={open} onOpenChange={value => {setOpen(value);if(!value)setSearch("");}}><Popover.Trigger asChild><button type="button" className="wv-add" aria-label={`Add ${label.toLowerCase()}`}><Ellipsis size={16}/><span>More</span></button></Popover.Trigger><Popover.Portal><Popover.Content className="wv-catalog" sideOffset={8} align="end" collisionPadding={12} aria-label="View catalogue">
      <header><div><strong>A fresh perspective</strong><p>Same workspace. A better way to see it.</p></div><Popover.Close className="wv-close" aria-label="Close view catalogue"><X size={16}/></Popover.Close></header>
      <label className="wv-search"><Search size={15}/><input autoFocus value={search} onChange={event => setSearch(event.target.value)} aria-label="Search workspace views" placeholder="Find a view..."/></label>
      <div className="wv-catalog-body">{(["Work", "Plan", "Collaborate", "Explore"] as const).map(category => { const items = available.filter(view => (view.category || "Work") === category); return items.length ? <section key={category}><h3>{category}</h3><div className="wv-catalog-grid">{items.map(view => <div className="wv-view-option" key={view.id}><span className="wv-view-icon" style={{color:view.color || "#7c3aed",background:`${view.color || "#7c3aed"}12`}}>{icon(view,19)}</span>{view.href ? <Link to={view.href} onClick={() => choose(view)}><strong>{view.label}</strong><small>{view.description}</small></Link> : <button type="button" onClick={() => choose(view)}><strong>{view.label}</strong><small>{view.description}</small></button>}<button type="button" className={`wv-pin ${pinned.includes(view.id) ? "pinned" : ""}`} aria-label={`${pinned.includes(view.id) ? "Unpin" : "Pin"} ${view.label} view`} aria-pressed={pinned.includes(view.id)} onClick={() => setPinned(current => current.includes(view.id) ? current.filter(id => id !== view.id) : [...current,view.id])}>{active === view.id ? <Check size={13}/> : <Star size={13}/>}</button></div>)}</div></section> : null; })}{!available.length && <div className="wv-no-results"><Search size={22}/><strong>No matching views</strong><p>Try a name such as Calendar, Channel or Gallery.</p></div>}</div>
      <footer><Star size={12}/><span>Pin your favourites. Your view bar is saved for this workspace.</span></footer>
    </Popover.Content></Popover.Portal></Popover.Root>
  </div>;
}
