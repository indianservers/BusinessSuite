import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, BookOpen, Building2, CalendarDays, ChevronDown, Flag, Handshake, HelpCircle, Home, Layers3, LayoutGrid, List, Network, Package, Search, Settings, ShieldCheck, ShoppingCart, Sparkles, Star, Users, UserRound, Zap, Filter } from "lucide-react";
import { SuiteIllustration } from "@/components/visuals/SuiteVisuals";
import { type ModuleIndexItem } from "@/lib/moduleCatalog";
import SuiteBrand from "./SuiteBrand";
import SuiteProfileMenu from "./SuiteProfileMenu";
import SuiteNotificationBell from "./SuiteNotificationBell";
import CompanySwitcher from "./CompanySwitcher";
import BranchSwitcher from "./BranchSwitcher";
import HomepageBanner from "./HomepageBanner";
import "./premium-launcher.css";

const highlights = {
  power_apps: [[LayoutGrid, "Low-code apps"], [Zap, "Automations"], [ShieldCheck, "Governance"]],
  hrms: [[UserRound, "Employee lifecycle"], [CalendarDays, "Attendance & Leave"], [Sparkles, "AI assist"]],
  crm: [[Filter, "Lead management"], [Handshake, "Deals & Pipeline"], [BarChart3, "Sales insights"]],
  pms: [[List, "Task & Sprint"], [Flag, "Milestones"], [BarChart3, "Reports"]],
  srm: [[ShoppingCart, "Sales & POS"], [Package, "Inventory & Stock"], [BarChart3, "Profitability"]],
  fam: [[BookOpen, "Accounts & Ledgers"], [Network, "Branches & Cost Centers"], [ShieldCheck, "Audit Ready"]],
} as const;

function Highlight({ text, query }: { text: string; query: string }) {
  const term = query.trim().toLowerCase();
  const start = term ? text.toLowerCase().indexOf(term) : -1;
  return start < 0 ? <>{text}</> : <>{text.slice(0, start)}<mark>{text.slice(start, start + term.length)}</mark>{text.slice(start + term.length)}</>;
}

export default function PremiumLauncher({ applications, authenticated = false, company, children, favorites = [], onFavorite, unread = {}, compact = false, onCompact, query, onQuery, favoritesOnly, onFavoritesOnly, onReorder, workspaceCount = 0, loading = false }: {
  applications: ModuleIndexItem[]; authenticated?: boolean; company?: string; children?: ReactNode;
  favorites?: string[]; onFavorite?: (key: string) => void; unread?: Record<string, number>;
  compact?: boolean; onCompact?: (value: boolean) => void;
  query?: string; onQuery?: (value: string) => void; favoritesOnly?: boolean;
  onFavoritesOnly?: (value: boolean) => void; onReorder?: (keys: string[]) => void;
  workspaceCount?: number; loading?: boolean;
}) {
  const [localQuery, setLocalQuery] = useState("");
  const [localFavoritesOnly, setLocalFavoritesOnly] = useState(false);
  const searchQuery = query ?? localQuery;
  const onlyFavorites = favoritesOnly ?? localFavoritesOnly;
  const setQuery = onQuery || setLocalQuery;
  const setFavoritesOnly = onFavoritesOnly || setLocalFavoritesOnly;
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [notice, setNotice] = useState<{ message: string; removed?: string; index?: number } | null>(null);
  const search = useRef<HTMLInputElement>(null);
  const searchBox = useRef<HTMLDivElement>(null);
  const appMenu = useRef<HTMLDetailsElement>(null);
  const navigate = useNavigate();
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);
  const destination = (m: ModuleIndexItem) => authenticated ? m.homePath : `/login?next=${encodeURIComponent(m.homePath)}`;
  const favoriteApps = favorites.filter(key => applications.some(m => m.key === key));
  const visible = applications.filter(m => !onlyFavorites || favorites.includes(m.key))
    .filter(m => `${m.key.replace(/_/g, " ")} ${m.name} ${m.label} ${m.description}`.toLowerCase().includes(searchQuery.trim().toLowerCase()))
    .sort((a, b) => (favorites.includes(a.key) ? favorites.indexOf(a.key) : Infinity) - (favorites.includes(b.key) ? favorites.indexOf(b.key) : Infinity));
  const visibleKeys = visible.map(m => m.key).join(",");
  useEffect(() => { setActive(0); }, [visibleKeys]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); if(appMenu.current)appMenu.current.open=false; search.current?.focus(); setOpen(true); }
      if (e.key === "Escape") { setOpen(false); search.current?.blur(); if(appMenu.current?.open){appMenu.current.open=false;appMenu.current.querySelector("summary")?.focus();} }
    };
    const outside = (e: PointerEvent) => { if (!searchBox.current?.contains(e.target as Node)) setOpen(false); if(appMenu.current && !appMenu.current.contains(e.target as Node))appMenu.current.open=false; };
    window.addEventListener("keydown", key); document.addEventListener("pointerdown", outside);
    return () => { window.removeEventListener("keydown", key); document.removeEventListener("pointerdown", outside); };
  }, []);
  useEffect(() => {
    if (open) document.getElementById(`launcher-result-${active}`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);
  const toggleFavorite = (m: ModuleIndexItem) => {
    const selected = favorites.includes(m.key);
    onFavorite?.(m.key);
    setNotice({ message: `${m.name} ${selected ? "removed from" : "added to"} favorites.`, removed: selected ? m.key : undefined, index: favorites.indexOf(m.key) });
  };
  const moveFavorite = (key: string, direction: number) => {
    const order = [...favorites];
    const target = favoriteApps[favoriteApps.indexOf(key) + direction];
    if (!target) return;
    const from = order.indexOf(key), to = order.indexOf(target);
    [order[from], order[to]] = [order[to], order[from]];
    onReorder?.(order); setNotice({ message: "Favorite order updated." });
  };
  return <div className={`premium-launcher${compact ? " launcher-compact" : ""}`}>
    <a className="suite-skip" href="#suite-main">Skip to applications</a>
    <header className="launcher-header">
      <SuiteBrand to={authenticated ? "/dashboard" : "/"}/>
      <nav className="launcher-nav" aria-label="Suite navigation">
        {!authenticated && <Link to="/signup">Sign up for a trial</Link>}
        <Link className="launcher-nav-home" to={authenticated ? "/dashboard" : "/"}><Home size={19}/>Home</Link>
        <details ref={appMenu} className="launcher-app-menu"><summary><LayoutGrid size={18}/>Applications<ChevronDown size={15}/></summary><div>{applications.map(m => <Link key={m.key} to={destination(m)} onClick={e => e.currentTarget.closest("details")?.removeAttribute("open")}><m.icon size={18}/>{m.name}</Link>)}</div></details>
        <Link to={authenticated ? "/company-admin" : "/login?next=%2Fcompany-admin"}><Settings size={19}/>Settings</Link>
      </nav>
      <div className="launcher-search-box" ref={searchBox}>
        <div className="launcher-search"><Search size={19}/><input ref={search} placeholder="Find an application..." aria-label="Search applications" role="combobox" aria-expanded={open} aria-controls="launcher-search-results" aria-autocomplete="list" aria-activedescendant={open && visible[active] ? `launcher-result-${active}` : undefined} value={searchQuery} onFocus={() => setOpen(true)} onChange={e => { setQuery(e.target.value); setActive(0); setOpen(true); }} onKeyDown={e => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setOpen(true); setActive(i => visible.length ? (i + (e.key === "ArrowDown" ? 1 : -1) + visible.length) % visible.length : 0); }
          if (e.key === "Enter" && visible[active]) { e.preventDefault(); setOpen(false); navigate(destination(visible[active])); }
        }}/>{searchQuery && <button aria-label="Clear application search" onClick={() => { setQuery(""); setActive(0); search.current?.focus(); }}>×</button>}<kbd>{mac ? "⌘K" : "Ctrl K"}</kbd></div>
        {open && <div className="launcher-search-results" id="launcher-search-results" role="listbox">{visible.map((m, i) => <Link role="option" aria-selected={active === i} id={`launcher-result-${i}`} key={m.key} to={destination(m)} onClick={() => setOpen(false)} onMouseEnter={() => setActive(i)}><m.icon size={19}/><span><Highlight text={m.name} query={searchQuery}/><small><Highlight text={m.label} query={searchQuery}/></small></span><ArrowRight size={16}/></Link>)}{!visible.length && <p>No matching applications. Try another name.</p>}</div>}
      </div>
      <div className="launcher-account"><Link className="launcher-help" to="/help"><HelpCircle size={19}/><span>Help</span></Link>{authenticated ? <><SuiteNotificationBell/><SuiteProfileMenu/></> : <Link className="launcher-signin" to="/login">Sign in</Link>}</div>
    </header>
    <main id="suite-main" tabIndex={-1}>
      <HomepageBanner company={company}/>
      <div className="launcher-body">
        {authenticated && <div className="launcher-company"><details className="launcher-view-options"><summary>View options</summary><div>{onCompact && <label><input type="checkbox" checked={compact} onChange={e => onCompact(e.target.checked)}/>Compact view</label>}</div></details><CompanySwitcher/><BranchSwitcher/></div>}
        {children}
        <section aria-labelledby="launcher-applications">
          <div className="launcher-section-head"><h2 id="launcher-applications">{authenticated ? "Your applications" : "Explore applications"}</h2><p>Access the tools your organization uses, all in one connected workspace.</p><div className="launcher-stats"><span><Layers3 size={18}/><b>{applications.length}</b> Applications</span>{authenticated && <span><Users size={19}/><b>{workspaceCount}</b> {workspaceCount === 1 ? "Workspace" : "Workspaces"}</span>}<span><Building2 size={19}/>{company || "Your Organization"}</span></div></div>
          {authenticated && <div className="launcher-filters" aria-label="Application filters"><button aria-pressed={!onlyFavorites} onClick={() => { setFavoritesOnly(false); setActive(0); }}>All applications</button><button aria-pressed={onlyFavorites} onClick={() => { setFavoritesOnly(true); setActive(0); }}><Star size={17}/>Favorites ({favoriteApps.length})</button><span role="status">{loading ? "Loading applications…" : `${visible.length} of ${applications.length} applications`}</span></div>}
          <div className="launcher-feedback" role="status" aria-live="polite">{notice && <>{notice.message} {notice.removed && <button onClick={() => {
            const order = [...favorites];
            if (!order.includes(notice.removed!)) {
              order.splice(notice.index ?? order.length, 0, notice.removed!);
              if (onReorder) onReorder(order); else onFavorite?.(notice.removed!);
            }
            setNotice({ message: "Favorite restored." });
          }}>Undo</button>}<button aria-label="Dismiss notification" onClick={() => setNotice(null)}>×</button></>}</div>
          {loading && <div className="launcher-loading" role="status" aria-label="Loading applications">{Array.from({ length: 6 }, (_, i) => <span key={i} aria-hidden="true"/>)}</div>}
          <div className="launcher-grid" aria-busy={loading}>{visible.map(m => <article key={m.key} aria-label={m.name} className={`launcher-card launcher-${m.key}`}>
            <div className="launcher-card-main"><span className="launcher-icon"><SuiteIllustration variant={m.key}/></span><div className="launcher-card-copy"><h3><Link className="launcher-card-link" to={destination(m)}><Highlight text={m.name} query={searchQuery}/></Link></h3><p className="launcher-category"><Highlight text={m.label} query={searchQuery}/></p><p className="launcher-description"><Highlight text={m.description} query={searchQuery}/></p></div><span className="launcher-arrow" aria-hidden="true"><ArrowRight size={21}/></span></div>
            <div className="launcher-features">{highlights[m.key as keyof typeof highlights]?.map(([Icon, label]) => <span key={label}><Icon size={18} strokeWidth={1.7}/>{label}</span>)}</div>
            <details className="launcher-description-details"><summary>About {m.name}</summary><p>{m.description}</p></details>
            {onReorder && favorites.includes(m.key) && <div className="launcher-favorite-order" aria-label={`Reorder ${m.name}`}><button aria-label={`Move ${m.name} earlier`} disabled={favoriteApps[0] === m.key} onClick={() => moveFavorite(m.key, -1)}>↑</button><button aria-label={`Move ${m.name} later`} disabled={favoriteApps[favoriteApps.length - 1] === m.key} onClick={() => moveFavorite(m.key, 1)}>↓</button></div>}
            {onFavorite && <button className="launcher-favorite" title={`${favorites.includes(m.key) ? "Remove from" : "Add to"} favorites: ${m.name}`} aria-label={`${favorites.includes(m.key) ? "Remove from" : "Add to"} favorites: ${m.name}`} aria-pressed={favorites.includes(m.key)} onClick={() => toggleFavorite(m)}><Star size={19} fill={favorites.includes(m.key) ? "currentColor" : "none"}/></button>}
            {!!unread[m.key] && <Link className="launcher-unread" to={`/notifications?app=${m.key}&unread=1`}>{unread[m.key]} updates</Link>}
          </article>)}</div>
          {!loading && !visible.length && applications.length > 0 && <div className="launcher-empty" role="status"><Search size={28}/><h3>{onlyFavorites ? "No matching favorite applications" : "No matching applications"}</h3><button onClick={() => { setQuery(""); setFavoritesOnly(false); setActive(0); }}>Show all applications</button></div>}
        </section>
        <Link to={authenticated ? "/company-admin" : "/login?next=%2Fcompany-admin"} className="launcher-settings"><span><Settings size={28}/></span><div><h2>Company Admin</h2><p>Settings, users, insights and analytics</p></div><ArrowRight size={25}/></Link>
      </div>
    </main>
  </div>;
}
