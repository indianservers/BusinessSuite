import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPath, parsePath, UNSAFE_LocationContext, UNSAFE_NavigationContext, type Location, type Navigator, type To, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { recordSavedEvent, type RecordSaved } from "@/lib/record-changes";
import type { FrontendRoute } from "@/appRegistry";
import { creationDefinition, contextualDestination, destinationPath, type CreationDefinition } from "./registry";
import { SmartCreateModal } from "./SmartCreateModal";
import { CreationContent } from "./CreationContent";
import { CreationDialogEnhancements } from "./CreationDialogEnhancements";
import ErrorBoundary from "@/components/app/ErrorBoundary";

type Frame = { key: string; location: Location; definition: CreationDefinition; onCreated?: (record?: unknown) => void; trigger: HTMLElement | null; scope: string; previousTitle: string; existingDialogs: HTMLElement[] };
type CreationApi = { open: (destination: string, onCreated?: (record?: unknown) => void) => boolean };
const CreationContext = createContext<CreationApi | null>(null);
function creationScope() {
  const actor = useAuthStore.getState().user;
  let organization: string | null = null, branch: string | null = null;
  try { organization = sessionStorage.getItem('suite-organization'); branch = sessionStorage.getItem('suite-branch'); } catch { /* Existing API access rules still apply when storage is unavailable. */ }
  return JSON.stringify([actor?.id, actor?.access?.companyId, organization, branch]);
}
export function useSmartCreation() { return useContext(CreationContext); }

/** A navigator adapter, not a second browser router: ordinary routes keep their original history and location. */
export function SmartCreationProvider({ children, routes }: { children: ReactNode; routes: FrontendRoute[] }) {
  const navigation = useContext(UNSAFE_NavigationContext);
  const location = useLocation();
  const user = useAuthStore(s => s.user);
  const [frames, setFrames] = useState<Frame[]>([]);
  const framesRef = useRef(frames); framesRef.current = frames;
  const active = useRef<Frame>(); active.current = frames[frames.length - 1];
  const identity = `${user?.id}:${user?.access?.companyId}`;
  useEffect(() => { active.current = undefined; framesRef.current = []; setFrames([]); }, [identity]);
  useEffect(() => {
    const clear = () => { active.current = undefined; framesRef.current = []; setFrames([]); };
    window.addEventListener("suite:organization-changed", clear);
    window.addEventListener("suite:branch-changed", clear);
    window.addEventListener("suite:record-access-changed", clear);
    return () => { window.removeEventListener("suite:organization-changed", clear); window.removeEventListener("suite:branch-changed", clear); window.removeEventListener("suite:record-access-changed", clear); };
  }, []);
  function open(destination: string, onCreated?: (record?: unknown) => void) {
    let url: URL;
    try { url = new URL(destination, window.location.origin); } catch { return false; }
    if (url.origin !== window.location.origin || !user) return false;
    const definition = creationDefinition(url.pathname + url.search + url.hash);
    if (!definition) return false;
    const grant = user.access?.grants[({ pms: "project_management" } as Record<string, string>)[url.pathname.split('/')[1]] || url.pathname.split('/')[1]];
    // A denied action stays denied. Its existing destination can show its access explanation.
    if (!canAccessRoute(url.pathname, user.role, user.is_superuser) || !user.is_superuser && grant && (!grant.enabled || !grant.actions.includes("create"))) return false;
    // Explicit related-record callers can stack a form and receive its saved record.
    // Parent frames remain mounted, so their drafts and selected fields survive.
    const path = contextualDestination(url.pathname + url.search + url.hash, active.current?.location || location);
    const resolved = parsePath(path);
    const next: Frame = { key: crypto.randomUUID(), definition: creationDefinition(path) || definition, location: { pathname: resolved.pathname!, search: resolved.search || "", hash: resolved.hash || "", state: null, key: "creation" }, scope: creationScope(), previousTitle: document.title, onCreated, trigger: document.activeElement instanceof HTMLElement ? document.activeElement : null, existingDialogs: Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')) };
    framesRef.current = [...framesRef.current, next]; active.current = next; setFrames(framesRef.current); return true;
  }
  const currentOpen = useRef(open); currentOpen.current = open;
  const adapted = useMemo<Navigator>(() => ({ ...navigation.navigator,
    push: (to, state, options) => { if (state?.suiteCanonicalRedirect) return navigation.navigator.push(to, state, options); if (active.current && creationDefinition(destinationPath(to))) { return; } if (!currentOpen.current(destinationPath(to))) navigation.navigator.push(to, state, options); },
    replace: (to, state, options) => { if (state?.suiteCanonicalRedirect) return navigation.navigator.replace(to, state, options); if (active.current && creationDefinition(destinationPath(to))) { return; } if (!currentOpen.current(destinationPath(to))) navigation.navigator.replace(to, state, options); },
  }), [navigation.navigator]);
  useEffect(() => {
    function capture(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const anchor = (event.target as Element)?.closest<HTMLAnchorElement>('a[href]');
      if (!anchor || anchor.hasAttribute('download') || anchor.closest('[role="dialog"]')) return;
      if (currentOpen.current(anchor.href)) { event.preventDefault(); event.stopPropagation(); }
    }
    document.addEventListener('click', capture, true);
    return () => document.removeEventListener('click', capture, true);
  }, []);
  function close(frame: Frame) {
    const current = framesRef.current;
    if (!current.some(item => item.key === frame.key)) return;
    const restoreTitle = active.current?.key === frame.key;
    const next = current.filter(item => item.key !== frame.key);
    framesRef.current = next;
    active.current = next[next.length - 1];
    setFrames(next);
    requestAnimationFrame(() => {
      if (restoreTitle && frame.trigger?.isConnected) frame.trigger.focus({ preventScroll: true });
      if (restoreTitle) document.title = frame.previousTitle;
    });
  }
  return <CreationContext.Provider value={{ open }}><UNSAFE_NavigationContext.Provider value={{ ...navigation, navigator: adapted }}>{children}</UNSAFE_NavigationContext.Provider>
    <CreationDialogEnhancements />
    {frames.map(frame => <CreationHost key={frame.key} frame={frame} routes={routes} close={() => close(frame)} />)}
  </CreationContext.Provider>;
}

function CreationHost({ frame, routes, close }: { frame: Frame; routes: FrontendRoute[]; close: () => void }) {
  const navigation = useContext(UNSAFE_NavigationContext);
  const creation = useSmartCreation();
  const [local, setLocal] = useState(frame.location), [busy, setBusy] = useState(false);
  const completed = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const confirmed = useRef(false);
  const [requestClose, setRequestClose] = useState(0);
  const [savedRevision, setSavedRevision] = useState(0);
  useEffect(() => {
    const saved = (event: Event) => {
      const change = (event as CustomEvent<RecordSaved>).detail;
      const entity = frame.definition.entity;
      const collection = ({ customer: 'companies', vendor: 'companies', company: 'companies', activity: 'activities', priceBook: 'price-books', quotation: 'quotations' } as Record<string, string>)[entity] || entity.replace(/([A-Z])/g, '-$1').toLowerCase() + 's';
      const path = change.url.split('?')[0].replace(/\/$/, '');
      if (change.method.toLowerCase() === "post" && path.endsWith('/' + collection) && (change.record?.id || (change.record?.task as { id?: number } | undefined)?.id)) confirmed.current = true;
    };
    window.addEventListener(recordSavedEvent, saved);
    return () => window.removeEventListener(recordSavedEvent, saved);
  }, [frame.definition.entity]);
  const complete = (record?: unknown, keepOpen = false) => {
    const captured = JSON.parse(frame.scope) as unknown[];
    const current = JSON.parse(creationScope()) as unknown[];
    // Initial branch discovery may hydrate an empty scope. Explicit scope-change events clear frames.
    if (!mounted.current || completed.current || captured.some((value, index) => value != null && value !== current[index])) return;
    if (!keepOpen) completed.current = true;
    // The existing API client publishes resource-scoped cache updates and counter invalidation.
    // Do not refetch those resources a second time when the dialog closes.
    const module = frame.location.pathname.split('/')[1];
    if (module === "crm") window.dispatchEvent(new Event('crm:records-changed'));
    window.dispatchEvent(new CustomEvent('suite:creation-completed', { detail: { destination: frame.location.pathname, entity: frame.definition.entity } }));
    frame.onCreated?.(record);
    if (keepOpen) setSavedRevision(revision => revision + 1); else close();
  };
  const completeRef = useRef(complete); completeRef.current = complete;
  useEffect(() => {
    const resource = ({ voucher: /\/fam\/vouchers\/?$/, purchase: /\/fam\/purchase-bills\/?$/, expense: /\/fam\/expenses\/?$/, purchaseOrder: /\/purchase-orders\/?$/, asset: /\/assets\/?$/, report: /\/analytics\/reports\/?$/, note: /\/project-management\/notes\/?$/, workspace: /\/project-management\/workspaces\/?$/, billOfMaterials: /\/srm\/inventory\/manufacturing\/bom\/?$/, productionOrder: /\/srm\/inventory\/manufacturing\/orders\/?$/ } as Record<string, RegExp>)[frame.definition.entity];
    if (!resource) return;
    const saved = (event: Event) => {
      const change = (event as CustomEvent<RecordSaved>).detail;
      if (change.method.toLowerCase() === 'post' && resource.test(change.url.split('?')[0]) && change.record?.id) completeRef.current(change.record);
    };
    window.addEventListener(recordSavedEvent, saved); return () => window.removeEventListener(recordSavedEvent, saved);
  }, [frame.definition.entity]);
  const navigateLocal = (to: To) => {
    const path = parsePath(destinationPath(to));
    const nextIntent = new URLSearchParams(path.search).get('new');
    // Scope hydration can retain the same creation intent while adding its workspace.
    // Keep that internal route update in this form instead of opening another copy.
    if ((!path.pathname || path.pathname === local.pathname) && nextIntent && nextIntent === new URLSearchParams(local.search).get('new')) {
      setLocal(current => ({ ...current, ...path, key: crypto.randomUUID() })); return;
    }
    if (creationDefinition(destinationPath(to)) && creation?.open(destinationPath(to))) return;
    // Creation intent consumers remove ?new after opening. Keep their page-scoped location isolated.
    if ((!path.pathname || path.pathname === local.pathname) && !path.search?.includes('new=')) {
      setLocal(current => ({ ...current, ...path, search: path.search || "", key: crypto.randomUUID() })); return;
    }
    if (confirmed.current) completeRef.current(); else setRequestClose(n => n + 1);
  };
  const localNavigator: Navigator = { ...navigation.navigator, push: navigateLocal, replace: navigateLocal, go: () => setRequestClose(n => n + 1), createHref: to => createPath(typeof to === 'string' ? parsePath(to) : to) };
  const content = <UNSAFE_NavigationContext.Provider value={{ ...navigation, navigator: localNavigator }}><UNSAFE_LocationContext.Provider value={{ location: local, navigationType: "POP" as import("react-router-dom").NavigationType }}><ErrorBoundary resetKey={frame.key}><CreationContent definition={frame.definition} routes={routes} close={frame.definition.presentation === "dialog" ? close : () => setRequestClose(n => n + 1)} complete={complete} busy={setBusy}/></ErrorBoundary></UNSAFE_LocationContext.Provider></UNSAFE_NavigationContext.Provider>;
  if (frame.definition.presentation === "dialog") return <ExistingCreationDialog close={close} existing={frame.existingDialogs} definition={frame.definition}>{content}</ExistingCreationDialog>;
  return <SmartCreateModal definition={frame.definition} onClose={close} busy={busy} savedRevision={savedRevision} closeRequestRevision={requestClose}>{content}</SmartCreateModal>;
}

/** Dialog adapters render their existing portal; never wrap them in a second uncontrolled dialog. */
function ExistingCreationDialog({ children, close, existing, definition }: { children: ReactNode; close: () => void; existing: HTMLElement[]; definition: CreationDefinition }) {
  const [phase, setPhase] = useState<'loading' | 'shown' | 'unavailable'>('loading');
  const observed = useRef(false);
  useEffect(() => {
    const inspect = () => {
      const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"]')).filter(dialog => !existing.includes(dialog) && !dialog.hasAttribute('data-smart-create-loading') && dialog.getAttribute('data-state') !== 'closed');
      if (dialogs.length) { observed.current = true; setPhase('shown'); }
      else if (observed.current && !['company', 'customer', 'vendor', 'lead', 'contact', 'deal', 'catalog'].includes(definition.entity)) close();
    };
    const observer = new MutationObserver(inspect); observer.observe(document.body, { childList: true, subtree: true }); inspect();
    const timeout = window.setTimeout(() => { if (!observed.current) setPhase('unavailable'); }, 8000);
    return () => { observer.disconnect(); window.clearTimeout(timeout); };
  }, [close, existing, definition.entity]);
  return <>{children}{phase !== 'shown' && <div className="smart-create-pending" role={phase === 'loading' ? 'status' : 'alert'}><span>{phase === 'loading' ? `Loading ${definition.entity} form…` : 'This form could not open. Close and try again, or check your access.'}</span><button type="button" onClick={close}>Cancel</button></div>}</>;
}
