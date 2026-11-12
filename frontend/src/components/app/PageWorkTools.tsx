import { useMobile } from "@/components/mobile/useMobile";
import { suiteScope, useSuitePreferences } from "@/store/suitePreferences";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { available, collectPageContext, type PageContextAction } from "@/lib/page-context-actions";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import "./page-work-tools.css";
import WritingActions from "@/components/ai-agents/WritingActions";

type Visit = { path: string; title: string };
/** Reuses page-owned controls: no parallel write paths or permissions. */
export default function PageWorkTools({portalScope,contextual=false}: {portalScope?: string;contextual?:boolean} = {}) {
  const location = useLocation();
  const mobile = useMobile();
  const user = useAuthStore(s => s.user);
  const savedRecent = useSuitePreferences(s=>s.contexts[suiteScope(user?.id,user?.access?.companyId)]?.recent);
  const context = portalScope || `${user?.access?.companyId ?? 0}:${user?.id ?? 0}`;
  const [open, setOpen] = useState(false), [query, setQuery] = useState("");
  const [actions, setActions] = useState<PageContextAction[]>([]), [visits, setVisits] = useState<Visit[]>([]);
  const [notice, setNotice] = useState("");
  const selected = useRef<PageContextAction>();
  const scope = `${context}:${location.pathname}${location.search}`;
  const scrollPositions = useRef(new Map<string, number>());
  const root = () => document.getElementById("suite-main") || document.querySelector<HTMLElement>("[data-route-content]") || document.querySelector<HTMLElement>("main");
  useLayoutEffect(() => {
    setOpen(false); setNotice("");
    // Contextual collections already use RouteContent for scroll restoration.
    if(contextual)return;
    // MobileExperience already owns scroll restoration in these mobile modules.
    if (mobile && /^\/(crm|pms|srm|hrms)(\/|$)/.test(location.pathname)) return;
    const main = root();
    let cachedTop = 0; try {cachedTop=Number(sessionStorage.getItem(`suite-page-position:${scope}`))||0;}catch{}
    const top = scrollPositions.current.get(scope) ?? cachedTop;
    let moved = top === 0;
    const restore = () => { if (!moved && main && main.scrollHeight >= top + main.clientHeight) { main.scrollTop = top; moved = true; } };
    restore();
    const observer = main ? new MutationObserver(restore) : null;
    if (main) observer?.observe(main, {childList:true,subtree:true});
    const stop = () => { moved = true; };
    main?.addEventListener("wheel", stop, { passive: true });
    main?.addEventListener("touchstart", stop, { passive: true });
    return () => { if (main) {scrollPositions.current.set(scope, main.scrollTop);try {sessionStorage.setItem(`suite-page-position:${scope}`,String(main.scrollTop));}catch{}} observer?.disconnect(); main?.removeEventListener("wheel", stop); main?.removeEventListener("touchstart", stop); };
  }, [scope,mobile,contextual]);
  useEffect(() => {
    if (!portalScope) return;
    const key = `suite-recent-pages:${context}`;
    const timer = window.setTimeout(() => {
      const title = root()?.querySelector("h1,h2")?.textContent?.trim() || location.pathname.split("/").filter(Boolean).join(" / ");
      try {
        const previous = JSON.parse(sessionStorage.getItem(key) || "[]") as Visit[];
        const path = location.pathname;
        const next = [{path, title}, ...previous.filter(v => v.path !== path)].slice(0, 20);
        sessionStorage.setItem(key, JSON.stringify(next)); setVisits(next);
      } catch { setVisits([]); }
    }, 600);
    return () => clearTimeout(timer);
  }, [scope]);
  function showActions() {
    const main = root();
    setActions(main ? collectPageContext(main, main)?.actions || [] : []);
    setQuery(""); setOpen(true);
  }
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if (event.defaultPrevented || (event.target as HTMLElement)?.closest("input,textarea,select,[contenteditable=true]")) return;
      if (Array.from(document.querySelectorAll('[role="dialog"]')).some(dialog => dialog.getClientRects().length > 0)) return;
      if (event.altKey && event.shiftKey && event.key.toLowerCase() === "a") { event.preventDefault(); showActions(); }

    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [scope]);
  const recent = (portalScope ? visits : (savedRecent || []).map(path=>({path,title:path.split("/").filter(Boolean).map(part=>part.replace(/-/g," ")).join(" / ")}))).filter(v => v.path !== location.pathname + location.search && v.path.startsWith("/") && !v.path.startsWith("//") && (portalScope ? v.path.startsWith(`/portal/${portalScope.split(":")[1]}`) : !v.path.startsWith("/portal/") && canAccessRoute(v.path.split("?")[0], user?.role, user?.is_superuser)));
  return <><div className={`page-work-tools${contextual?" page-work-tools-contextual":""}`} data-context-menu-ignore data-page-work-tools>
    <WritingActions presentation="menu"/>
    <button type="button" onClick={showActions} aria-keyshortcuts="Alt+Shift+A" title="Page actions and keyboard shortcuts (Alt+Shift+A)">Page actions</button>
    {notice && <span role="status" className="sr-only">{notice}</span>}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="page-actions-dialog" onCloseAutoFocus={event => { const action = selected.current; selected.current = undefined; if (action) { event.preventDefault(); requestAnimationFrame(() => { if (available(action.source)) action.run(); }); } }}>
      <DialogTitle>Page actions</DialogTitle>
      <p className="text-sm text-muted-foreground">Alt+Shift+A opens actions · Escape closes this panel</p>
      <input autoFocus aria-label="Find page action" placeholder="Find an action…" value={query} onChange={event => setQuery(event.target.value)} className="rounded border bg-background p-2" />
      <div className="page-actions-list">{actions.filter(a => a.label.toLowerCase().includes(query.toLowerCase())).map(action => <button type="button" key={action.label} onClick={() => { selected.current = action; setOpen(false); }}>{action.label}</button>)}</div>
      {!actions.length && <p className="text-sm text-muted-foreground">This page has no available actions. Open a record to see its controls.</p>}
      <button type="button" onClick={() => { void navigator.clipboard.writeText(window.location.href).then(() => setNotice("Page link copied"), () => setNotice("Could not copy page link")); }}>Copy page link</button>
      {!!recent.length && <section><h3 className="font-medium">Recently visited</h3><nav className="page-actions-list" aria-label="Recently visited pages">{recent.filter(v => v.title.toLowerCase().includes(query.toLowerCase())).slice(0, 8).map(v => <Link key={v.path} to={v.path} onClick={() => setOpen(false)}>{v.title}</Link>)}</nav></section>}
    </DialogContent></Dialog>
  </div></>;
}
