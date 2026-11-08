import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Building2, Ellipsis, FolderKanban, Layers3, LayoutGrid, List, Plus, Search, ShieldCheck, Star, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useAuthStore } from "@/store/authStore";
import "./workspace-directory.css";

export type DirectoryEntry = {
  id: string; name: string; description?: string; href: string;
  icon?: LucideIcon; category?: string; role?: string; owner?: string; members?: number;
  links?: { label: string; href: string }[]; facts?: { label: string; value: string | number }[]; createdAt?: string; status?: string; projects?: number; tasks?: number; completedTasks?: number;
};
export type DirectoryAction = { label: string; href: string; icon: LucideIcon };
export type DirectoryMetric = { label: string; value: string | number; icon: LucideIcon };
type Preferences = { view: "grid" | "list"; favorites: string[]; sort: string };
function readPreferences(key: string): Preferences {
  try {
    const data = JSON.parse(localStorage.getItem(key) || "{}");
    return { view: data.view === "list" ? "list" : "grid", favorites: Array.isArray(data.favorites) ? data.favorites.filter((id: unknown) => typeof id === "string") : [], sort: ["name", "created"].includes(data.sort) ? data.sort : "name" };
  } catch { return { view: "grid", favorites: [], sort: "name" }; }
}

/** Domain adapters supply only authorized data and supported actions. */
export function WorkspaceDirectory(props: {
  module: string; title: string; description: string; icon: LucideIcon;
  entries: DirectoryEntry[]; actions?: DirectoryAction[]; loading?: boolean;
  error?: string; onRetry?: () => void; onCreate?: () => void;
  createLabel?: string; notice?: string; children?: ReactNode;
  metrics?: DirectoryMetric[];
}) {
  const user = useAuthStore(s => s.user);
  let branch = "", organization = "";
  try { branch = sessionStorage.getItem("suite-branch") || ""; organization = sessionStorage.getItem("suite-organization") || ""; } catch { /* Optional storage. */ }
  const key = `suite:workspace-directory:v1:${user?.id}:${user?.access?.companyId}:${organization}:${branch}:${props.module}`;
  return <DirectoryContent key={key} {...props} preferenceKey={key} company={user?.access?.companyName} branch={branch} />;
}

function DirectoryContent({ module, title, description, icon: Icon, entries, actions = [], loading, error, onRetry, onCreate, createLabel = "Create Workspace", notice, children, metrics = [], preferenceKey, company, branch }: Parameters<typeof WorkspaceDirectory>[0] & { preferenceKey: string; company?: string; branch: string }) {
  const [preferences, setPreferences] = useState(() => readPreferences(preferenceKey));
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  function update(next: Preferences) { setPreferences(next); try { localStorage.setItem(preferenceKey, JSON.stringify(next)); } catch { /* Keep the current view usable. */ } }
  const categories = [...new Set(entries.map(entry => entry.category).filter((value): value is string => Boolean(value)))];
  const favorites = entries.filter(entry => preferences.favorites.includes(entry.id));
  const visible = entries.filter(entry => `${entry.name} ${entry.description || ""}`.toLowerCase().includes(query.trim().toLowerCase()) && (filter === "all" || filter === "favorites" && preferences.favorites.includes(entry.id) || entry.category === filter)).sort((a, b) => preferences.sort === "created" ? (b.createdAt || "").localeCompare(a.createdAt || "") || a.name.localeCompare(b.name) : a.name.localeCompare(b.name));
  const hasLinks = entries.some(entry => entry.links?.length);
  const hasOwner = entries.some(entry => entry.owner);
  const hasTasks = entries.some(entry => entry.tasks != null);
  const hasMembers = entries.some(entry => entry.members != null);
  const allMembersKnown = entries.length > 0 && entries.every(entry => entry.members != null);
  const allTasksKnown = entries.length > 0 && entries.every(entry => entry.tasks != null);
  const canSortCreated = entries.some(entry => entry.createdAt);
  const toggleFavorite = (id: string) => update({ ...preferences, favorites: preferences.favorites.includes(id) ? preferences.favorites.filter(value => value !== id) : [...preferences.favorites, id] });
  return <main className="workspace-directory" aria-busy={loading || undefined}>
    <nav className="wd-breadcrumb" aria-label="Breadcrumb"><Link to={`/${module}`}>Home</Link><span aria-hidden="true">/</span><span>Workspaces</span></nav>
    <header className="wd-hero">
      <span className="wd-hero-icon"><Icon size={30} /></span>
      <div className="wd-hero-copy"><h1>{title}</h1><p>{description}</p><div className="wd-context">{company && <span><Building2 size={14} />{company}</span>}{branch && <span>Branch {branch}</span>}<span><ShieldCheck size={14} />Your authorized spaces</span></div></div>
      <div className="wd-illustration" aria-hidden="true"><div className="wd-illustration-window"><i /><i /><i /><div>{[Icon, Users, Layers3, ShieldCheck].map((Tile, index) => <span key={index}><Tile size={22} /><b /></span>)}</div></div><span className="wd-illustration-orbit"><Icon size={26} /></span></div>
    </header>
    <section className="wd-summary" aria-label="Workspace summary">
      <div><Layers3 /><span>{module === "pms" ? "Available workspaces" : "Operational workspaces"}<strong>{(loading || error) && !entries.length ? "—" : entries.length}</strong></span></div>
      <div><Star /><span>Favorites<strong>{favorites.length}</strong></span></div>
      {allMembersKnown && <div><Users /><span>Workspace memberships<strong>{entries.reduce((total, entry) => total + (entry.members || 0), 0)}</strong></span></div>}
      {allTasksKnown && <div><FolderKanban /><span>Total tasks<strong>{entries.reduce((total, entry) => total + (entry.tasks || 0), 0)}</strong></span></div>}
      {metrics.map(metric => <div key={metric.label}><metric.icon /><span>{metric.label}<strong className={typeof metric.value === "string" ? "wd-summary-label" : undefined}>{metric.value}</strong></span></div>)}
      {!metrics.length && <div><ShieldCheck /><span>Access<strong className="wd-summary-label">Your current access</strong></span></div>}
    </section>
    {notice && <p className="wd-notice">{notice}</p>}
    <div className="wd-toolbar">
      <label className="wd-search"><Search size={19} /><Input aria-label="Search workspaces" placeholder="Find a workspace by name or description…" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <div className="wd-filters" aria-label="Workspace filters"><button type="button" aria-pressed={filter === "all"} onClick={() => setFilter("all")}>All ({entries.length})</button><button type="button" aria-pressed={filter === "favorites"} onClick={() => setFilter("favorites")}><Star size={14} />Favorites ({favorites.length})</button>{categories.map(category => <button key={category} type="button" aria-pressed={filter === category} onClick={() => setFilter(category)}>{category}</button>)}</div>
      <div className="wd-view-controls"><select aria-label="Sort workspaces" value={preferences.sort} onChange={event => update({ ...preferences, sort: event.target.value })}><option value="name">Name A–Z</option>{canSortCreated && <option value="created">Newest first</option>}</select><div className="wd-view-toggle" aria-label="Workspace view">{(["grid", "list"] as const).map(view => <button key={view} type="button" aria-label={`${view === "grid" ? "Grid" : "List"} view`} aria-pressed={preferences.view === view} onClick={() => update({ ...preferences, view })}>{view === "grid" ? <LayoutGrid size={18} /> : <List size={18} />}</button>)}</div>{onCreate && <Button onClick={onCreate}><Plus size={17} />{createLabel}</Button>}</div>
    </div>
    {error && <div role="alert" className="wd-error"><span>{error}</span>{onRetry && <Button variant="outline" onClick={onRetry}>Retry</Button>}</div>}
    {loading && !entries.length ? <section className="wd-grid" role="status" aria-label={`Loading ${title}`}>{[1, 2, 3].map(id => <div className="wd-skeleton" key={id}><span /><span /><span /></div>)}</section> : <>
      <p className="sr-only" role="status">{visible.length} workspaces shown</p>
      <section aria-label="Workspace list" className={preferences.view === "grid" ? "wd-grid" : "wd-list"}>
        {preferences.view === "grid" ? visible.map(entry => {
          const EntryIcon = entry.icon || FolderKanban;
          return <article className={`wd-card ${entry.links?.length ? "wd-card-with-menu" : ""}`} key={entry.id}><Link className="wd-card-link" to={entry.href}><div className="wd-card-heading"><span className="wd-card-icon"><EntryIcon size={27} /></span><div><h2>{entry.name}</h2><span className="wd-card-category">{entry.category || entry.role || "Workspace"}</span></div></div><p className="wd-card-description">{entry.description || "Projects, tasks and collaboration in one dedicated space."}</p>{entry.owner && <p className="wd-owner" title={`Owner: ${entry.owner}`}><Users size={13} /><span>Owner: {entry.owner}</span></p>}<div className="wd-domain-metrics">{entry.facts?.map(fact => <span key={fact.label}><strong>{fact.value}</strong> {fact.label}</span>)}{entry.projects != null && <span><FolderKanban size={14} />{entry.projects} {entry.projects === 1 ? "project" : "projects"}</span>}{entry.tasks != null && <span>{entry.tasks} {entry.tasks === 1 ? "task" : "tasks"}</span>}{entry.tasks != null && entry.tasks > 0 && entry.completedTasks != null && <span className="wd-progress"><progress aria-label={`${entry.name} task completion`} value={entry.completedTasks} max={entry.tasks} />{Math.round(entry.completedTasks / entry.tasks * 100)}%</span>}</div><footer>{entry.members != null && <span><Users size={16} />{entry.members} {entry.members === 1 ? "member" : "members"}</span>}{entry.status && <span className="wd-status">{entry.status}</span>}{entry.createdAt && <time dateTime={entry.createdAt}>Created {new Date(entry.createdAt).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</time>}<ArrowRight size={17} className="wd-open-arrow" /></footer></Link><button className="wd-favorite" type="button" aria-label={`${preferences.favorites.includes(entry.id) ? "Unfavorite" : "Favorite"} ${entry.name}`} aria-pressed={preferences.favorites.includes(entry.id)} onClick={() => toggleFavorite(entry.id)}><Star size={17} /></button>{entry.links?.length ? <EntryMenu entry={entry} /> : null}</article>;
        }) : visible.length > 0 && <div className="wd-table-scroll"><table><thead><tr><th>Workspace</th><th>Access / Category</th>{hasOwner && <th>Owner</th>}{hasTasks && <th>Tasks</th>}{hasMembers && <th>Members</th>}<th>Favorite</th>{hasLinks && <th>Actions</th>}</tr></thead><tbody>{visible.map(entry => <tr key={entry.id}><td><Link to={entry.href}><strong>{entry.name}</strong><small>{entry.description}</small></Link></td><td>{entry.role || entry.category || "Authorized"}</td>{hasOwner && <td>{entry.owner || "—"}</td>}{hasTasks && <td>{entry.tasks ?? "—"}</td>}{hasMembers && <td>{entry.members ?? "—"}</td>}<td><button className="wd-table-favorite" type="button" aria-label={`${preferences.favorites.includes(entry.id) ? "Unfavorite" : "Favorite"} ${entry.name}`} aria-pressed={preferences.favorites.includes(entry.id)} onClick={() => toggleFavorite(entry.id)}><Star size={17} /></button></td>{hasLinks && <td>{entry.links?.length ? <EntryMenu entry={entry} /> : null}</td>}</tr>)}</tbody></table></div>}
        {!visible.length && !error && <div className="wd-empty"><Layers3 size={35} /><h2>{query || filter !== "all" ? "No matching workspaces" : "Your next space starts here"}</h2><p>{query || filter !== "all" ? "Try another search or clear your filters." : "Workspaces available to your account will appear here."}</p>{(query || filter !== "all") && <Button variant="outline" onClick={() => { setQuery(""); setFilter("all"); }}>Clear filters</Button>}{!query && filter === "all" && onCreate && <Button onClick={onCreate}><Plus size={16} />{createLabel}</Button>}</div>}
      </section>
    </>}
    {actions.length > 0 && <section className="wd-quick-actions" aria-label="Quick actions"><div><h2>Quick actions</h2><p>Keep work moving</p></div><div>{actions.map(action => <Link to={action.href} key={action.href}><span><action.icon size={21} /></span><strong>{action.label}</strong><ArrowRight size={15} /></Link>)}</div></section>}
    {children}
  </main>;
}

function EntryMenu({ entry }: { entry: DirectoryEntry }) {
  const [open, setOpen] = useState(false);
  return <Popover open={open} onOpenChange={setOpen}><PopoverTrigger asChild><button type="button" className="wd-entry-menu" aria-label={`Actions for ${entry.name}`}><Ellipsis size={18} /></button></PopoverTrigger><PopoverContent align="end" className="wd-entry-menu-content"><nav aria-label={`${entry.name} actions`}>{entry.links?.map(link => <Link key={link.href} to={link.href} onClick={() => setOpen(false)}>{link.label}<ArrowRight size={14} /></Link>)}</nav></PopoverContent></Popover>;
}
