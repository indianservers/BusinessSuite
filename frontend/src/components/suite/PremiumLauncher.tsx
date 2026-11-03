import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, BookOpen, Building2, CalendarDays, ChevronDown, Flag, Handshake, HelpCircle, Home, Layers3, LayoutGrid, List, Network, Package, Search, Settings, ShieldCheck, ShoppingCart, Sparkles, Star, Users, UserRound, Zap, Filter } from "lucide-react";
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

export default function PremiumLauncher({ applications, authenticated = false, company, children, favorites, onFavorite, unread = {}, compact = false, onCompact }: {
  applications: ModuleIndexItem[]; authenticated?: boolean; company?: string; children?: ReactNode;
  favorites?: string[]; onFavorite?: (key: string) => void; unread?: Record<string, number>;
  compact?: boolean; onCompact?: (value: boolean) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const searchBox = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const destination = (m: ModuleIndexItem) => authenticated ? m.homePath : `/login?next=${encodeURIComponent(m.homePath)}`;
  const visible = applications.filter(m => !favoritesOnly || favorites?.includes(m.key))
    .filter(m => `${m.name} ${m.label} ${m.description}`.toLowerCase().includes(query.trim().toLowerCase()))
    .sort((a, b) => Number(favorites?.includes(b.key)) - Number(favorites?.includes(a.key)));
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); search.current?.focus(); setOpen(true); }
      if (e.key === "Escape") { setOpen(false); search.current?.blur(); }
    };
    const outside = (e: PointerEvent) => { if (!searchBox.current?.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("keydown", key); document.addEventListener("pointerdown", outside);
    return () => { window.removeEventListener("keydown", key); document.removeEventListener("pointerdown", outside); };
  }, []);
  return <div className={`premium-launcher${compact ? " launcher-compact" : ""}`}>
    <a className="suite-skip" href="#suite-main">Skip to applications</a>
    <header className="launcher-header">
      <SuiteBrand to={authenticated ? "/dashboard" : "/"} />
      <nav className="launcher-nav" aria-label="Suite navigation">
        <Link className="launcher-nav-home" to={authenticated ? "/dashboard" : "/"}><Home size={19} />Home</Link>
        <details className="launcher-app-menu"><summary><LayoutGrid size={18} />Applications<ChevronDown size={15} /></summary><div>{applications.map(m => <Link key={m.key} to={destination(m)} onClick={e => e.currentTarget.closest("details")?.removeAttribute("open")}><m.icon size={18} />{m.name}</Link>)}</div></details>
        <Link to={authenticated ? "/settings" : "/login?next=%2Fsettings"}><Settings size={19} />Settings</Link>
      </nav>
      <div className="launcher-search-box" ref={searchBox}>
        <div className="launcher-search"><Search size={19} /><input ref={search} placeholder="Find an application..." aria-label="Search applications" role="combobox" aria-expanded={open} aria-controls="launcher-search-results" aria-autocomplete="list" aria-activedescendant={open && visible[active] ? `launcher-result-${active}` : undefined} value={query} onFocus={() => setOpen(true)} onChange={e => { setQuery(e.target.value); setActive(0); setOpen(true); }} onKeyDown={e => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); setOpen(true); setActive(i => visible.length ? (i + (e.key === "ArrowDown" ? 1 : -1) + visible.length) % visible.length : 0); }
          if (e.key === "Enter" && visible[active]) { e.preventDefault(); setOpen(false); navigate(destination(visible[active])); }
        }} /><kbd>Ctrl K</kbd></div>
        {open && <div className="launcher-search-results" id="launcher-search-results" role="listbox">{visible.map((m, i) => <Link role="option" aria-selected={active === i} id={`launcher-result-${i}`} key={m.key} to={destination(m)} onClick={() => setOpen(false)} onMouseEnter={() => setActive(i)}><m.icon size={19} /><span>{m.name}<small>{m.label}</small></span><ArrowRight size={16} /></Link>)}{!visible.length && <p>No matching applications. Try another name.</p>}</div>}
      </div>
      <div className="launcher-account"><Link className="launcher-help" to="/help"><HelpCircle size={19} /><span>Help</span></Link>{authenticated ? <><SuiteNotificationBell /><SuiteProfileMenu /></> : <Link className="launcher-signin" to="/login">Sign in</Link>}</div>
    </header>
    <main id="suite-main" tabIndex={-1}>
      <HomepageBanner company={company} />
      <div className="launcher-body">
        {authenticated && <div className="launcher-company"><details className="launcher-view-options"><summary>View options</summary><div><label><input type="checkbox" checked={favoritesOnly} onChange={e => { setFavoritesOnly(e.target.checked); setActive(0); }} />Favorites only</label>{onCompact && <label><input type="checkbox" checked={compact} onChange={e => onCompact(e.target.checked)} />Compact view</label>}</div></details><CompanySwitcher /><BranchSwitcher /></div>}
        {children}
        <section aria-labelledby="launcher-applications">
          <div className="launcher-section-head"><h2 id="launcher-applications">{authenticated ? "Your applications" : "Explore applications"}</h2><p>Access the tools your organization uses, all in one connected workspace.</p><div className="launcher-stats"><span><Layers3 size={18} /><b>{applications.length}</b> Applications</span><span><Users size={19} /><b>1</b> Workspace</span><span><Building2 size={19} />{company || "Your Organization"}</span></div></div>
          <div className="launcher-grid">{visible.map(m => <article key={m.key} className={`launcher-card launcher-${m.key}`}>
            <div className="launcher-card-main"><span className="launcher-icon"><m.icon size={35} strokeWidth={1.8} /></span><div className="launcher-card-copy"><h3><Link className="launcher-card-link" to={destination(m)}>{m.name}</Link></h3><p className="launcher-category">{m.label}</p><p className="launcher-description">{m.description}</p></div><span className="launcher-arrow" aria-hidden="true"><ArrowRight size={21} /></span></div>
            <div className="launcher-features">{highlights[m.key as keyof typeof highlights]?.map(([Icon, label]) => <span key={label}><Icon size={18} strokeWidth={1.7} />{label}</span>)}</div>
            {onFavorite && <button className="launcher-favorite" aria-label={`${favorites?.includes(m.key) ? "Unpin" : "Pin"} ${m.name}`} aria-pressed={favorites?.includes(m.key) || false} onClick={() => onFavorite(m.key)}><Star size={13} fill={favorites?.includes(m.key) ? "currentColor" : "none"} /></button>}
            {!!unread[m.key] && <Link className="launcher-unread" to={`/notifications?app=${m.key}&unread=1`}>{unread[m.key]} updates</Link>}
          </article>)}</div>
          {!visible.length && applications.length > 0 && <div className="launcher-empty" role="status"><Search size={28} /><h3>{favoritesOnly ? "No matching favorite applications" : "No matching applications"}</h3><button onClick={() => { setQuery(""); setFavoritesOnly(false); setActive(0); }}>Show all applications</button></div>}
        </section>
        <Link to={authenticated ? "/settings" : "/login?next=%2Fsettings"} className="launcher-settings"><span><Settings size={28} /></span><div><h2>Settings</h2><p>Company details, branches, users and permissions</p></div><ArrowRight size={25} /></Link>
      </div>
    </main>
  </div>;
}
