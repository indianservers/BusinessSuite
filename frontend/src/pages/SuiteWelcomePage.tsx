import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, ChevronDown, HelpCircle, Home, Layers3, LayoutGrid, Search, Settings, ShieldCheck, Users, BarChart3, UserRound } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import SuiteBrand from "@/components/suite/SuiteBrand";
import HomeApplicationCard from "@/components/suite/HomeApplicationCard";
import HomeAuthPanel from "@/components/suite/HomeAuthPanel";
import { homeApplications, homeCategories } from "@/components/suite/homeApplications";
import { loginDestination } from "@/lib/login";
import workspaceArtwork from "@/assets/suite/suite-home-workspace.webp";
import "./suite-welcome.css";

export default function SuiteWelcomePage() {
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All apps");
  const [mobile, setMobile] = useState(() => matchMedia("(max-width: 800px)").matches);
  const [mobileAuth, setMobileAuth] = useState(() => params.has("auth") || params.has("next") || params.has("recover"));
  const [allApps, setAllApps] = useState(false);
  const search = useRef<HTMLInputElement>(null);
  const mobileLogin = useRef<HTMLButtonElement>(null);
  const signup = params.get("auth") === "signup";
  const destination = loginDestination(params.get("next"));

  useEffect(() => {
    const media = matchMedia("(max-width: 800px)");
    const resize = () => setMobile(media.matches);
    media.addEventListener("change", resize);
    const shortcut = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => { media.removeEventListener("change", resize); window.removeEventListener("keydown", shortcut); };
  }, []);
  useEffect(() => {
    if (!mobile || !mobileAuth) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previous; };
  }, [mobile, mobileAuth]);

  function switchAuth(value: boolean) {
    setParams(old => {
      const next = new URLSearchParams(old);
      value ? next.set("auth", "signup") : next.delete("auth");
      return next;
    }, { replace: true });
  }
  function openAuth(value: boolean) {
    switchAuth(value);
    if (mobile) setMobileAuth(true);
    else document.getElementById("home-auth")?.scrollIntoView({ block: "nearest" });
  }
  function select(path: string) {
    setParams(old => {
      const next = new URLSearchParams(old);
      next.set("next", path);
      next.delete("auth");
      return next;
    }, { replace: true });
    if (mobile) setMobileAuth(true);
    else {
      document.getElementById("home-auth")?.scrollIntoView({
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "nearest",
      });
      requestAnimationFrame(() => document.getElementById("email")?.focus({ preventScroll: true }));
    }
  }
  const filtered = homeApplications.filter(app =>
    (category === "All apps" || app.category === category) &&
    `${app.title} ${app.description} ${app.chips.map(chip => chip[1]).join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const ordered = mobile ? [...filtered].sort((a, b) => Number(b.key === "appointments") - Number(a.key === "appointments")) : filtered;
  const visible = mobile && !allApps && category === "All apps" && !query.trim() ? ordered.slice(0, 4) : ordered;
  const categoryIcons = [LayoutGrid, Layers3, UserRound, Users, BarChart3];
  const selectedName = homeApplications.find(app => app.module.homePath === destination)?.title || (destination === "/company-admin" ? "Company Admin" : "your selected workspace");
  const authPanel = <>{destination !== "/dashboard" && <p className="home-destination" role="status">Continue to {selectedName} after sign-in.</p>}<HomeAuthPanel signup={signup} onChange={switchAuth}/></>;

  return <div className="suite-welcome">
    <a className="suite-skip" href="#home-applications">Skip to applications</a>
    <header className="home-header">
      <SuiteBrand/>
      <nav aria-label="Main navigation">
        <a href="#home-applications" className="home-workspace"><Home size={19}/>Workspace</a>
        <details><summary><LayoutGrid size={19}/>Applications<ChevronDown size={14}/></summary><div>{homeApplications.map(app =>
          <a key={app.key} href={`/?next=${encodeURIComponent(app.module.homePath)}#home-auth`} onClick={event => {
            event.preventDefault(); event.currentTarget.closest("details")?.removeAttribute("open"); select(app.module.homePath);
          }}>{app.title}</a>,
        )}</div></details>
        <Link to="/help"><HelpCircle size={19}/>Help</Link>
      </nav>
      <label className="home-header-search"><Search size={18}/><input aria-label="Search applications from header" placeholder="Search applications, features, or help..." value={query} onChange={event => { setQuery(event.target.value); setCategory("All apps"); }}/><kbd>Ctrl K</kbd></label>
      <button ref={mobileLogin} className="home-mobile-login" onClick={() => openAuth(false)}>Log in</button>
      <button className="home-primary" onClick={() => openAuth(true)}>Get started</button>
    </header>
    <main className="home-layout">
      <div className="home-content">
        <section className="home-hero">
          <div><h1>One workspace. Every possibility.</h1><p>Your people, customers and operations. Beautifully connected.</p><ul><li><Layers3/>Unify operations</li><li><Users/>Empower teams</li><li><ShieldCheck/>Enterprise-grade security</li></ul></div>
          <img src={workspaceArtwork} alt="" width="600" height="400" fetchPriority="high"/>
        </section>
        <section id="home-applications" aria-labelledby="home-app-title">
          <div className="home-section-heading"><h2 id="home-app-title">Explore your applications</h2><p>Access the tools your organization uses, all in one connected workspace.</p></div>
          <div className="home-app-tools">
            <label className="home-app-search"><Search size={18}/><input ref={search} aria-label="Search applications" placeholder="Search applications..." value={query} onChange={event => setQuery(event.target.value)}/>{query && <button aria-label="Clear search" onClick={() => setQuery("")}>×</button>}</label>
            <div className="home-categories" aria-label="Application categories">{homeCategories.map((label, index) => {
              const Icon = categoryIcons[index];
              return <button key={label} aria-pressed={category === label} onClick={() => setCategory(label)}><Icon size={17}/>{label}</button>;
            })}</div>
          </div>
          <div className="home-app-grid">{visible.map(app => <HomeApplicationCard key={app.key} app={app} selected={destination === app.module.homePath} onSelect={select}/>)}</div>
          {mobile && category === "All apps" && !query.trim() && <button className="home-show-apps" aria-expanded={allApps} onClick={() => setAllApps(value => !value)}>{allApps ? "Show fewer" : "Show all 7 applications"}<ChevronDown size={16}/></button>}
          {!visible.length && <div className="home-empty" role="status">No applications match your search. <button onClick={() => { setQuery(""); setCategory("All apps"); }}>Show all applications</button></div>}
          <span className="sr-only" role="status">{visible.length} applications shown</span>
        </section>
        <a className="home-admin" href="/?next=%2Fcompany-admin#home-auth" onClick={event => { event.preventDefault(); select("/company-admin"); }}><span><Settings size={27}/></span><div><h3>Company Admin</h3><p>Settings, users, insights and analytics for your organization.</p></div><ArrowRight size={22}/></a>
      </div>
      {!mobile && <div className="home-auth-column">{authPanel}</div>}
    </main>
    {mobile && <Dialog open={mobileAuth} onOpenChange={setMobileAuth}><DialogContent className="suite-welcome home-mobile-auth-dialog" onCloseAutoFocus={event => { event.preventDefault(); mobileLogin.current?.focus(); }}><DialogTitle className="sr-only">Log in or request trial access</DialogTitle>{authPanel}</DialogContent></Dialog>}
    <footer className="home-footer"><span>🇮🇳 Indian Servers</span><div><Link to="/signup?policy=privacy">Privacy</Link><Link to="/signup?policy=terms">Terms</Link><Link to="/help">Help</Link></div></footer>
  </div>;
}
