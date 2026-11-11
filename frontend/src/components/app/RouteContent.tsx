import RecordFreshness from "./RecordFreshness";
import { useLayoutEffect, useRef, type ReactNode } from "react";
import { useLocation, useNavigate, useNavigationType } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { stable } from "@/lib/smart-cache/model";
import { navigationViews, presentationSearch } from "@/lib/navigation-views";
import "./route-content.css";
/** Retain the shell and bounded UI metadata, without keeping inactive page trees alive. */
export default function RouteContent({ children }: { children: ReactNode }) {
  const content = useRef<HTMLDivElement>(null),
    location = useLocation(),
    navigate = useNavigate(),
    action = useNavigationType();
  const user = useAuthStore((s) => s.user);
  const scope = stable([
    user?.id,
    user?.primary_role ?? user?.role,
    user?.access,
    sessionStorage.getItem("suite-tenant"),
    sessionStorage.getItem("suite-organization"),
    sessionStorage.getItem("suite-branch"),
  ]);
  navigationViews.scope(scope);
  useLayoutEffect(() => {
    const element = content.current,
      scroll = element?.closest<HTMLElement>(
        "[data-navigation-scroll],#suite-main",
      );
    if (!element || !scroll) return;
    // Forms already own draft/navigation guards. Do not replay action query parameters.
    const form = /\/(?:new|edit)(?:\/|$)/.test(location.pathname);
    const key = location.pathname;
    const saved = navigationViews.get(key);
    if (!form && action === "PUSH" && !location.search && saved?.search) {
      navigate(
        { pathname: key, search: saved.search, hash: location.hash },
        { replace: true },
      );
      return;
    }
    const restore =
      !form && saved && saved.search === presentationSearch(location.search)
        ? saved
        : undefined;
    let pending = !!restore,
      frame = 0;
    let recordFocus = restore?.recordFocus;
    let focusPending = action === "POP" && !!recordFocus;
    // Route children can shrink the scroll container before layout-effect cleanup.
    // Retain the last observed position rather than saving that clamped DOM value.
    let position = { top: restore?.scrollTop || 0, left: restore?.scrollLeft || 0 };
    const apply = () => {
      if (pending) scroll.scrollTo({
        top: restore!.scrollTop,
        left: restore!.scrollLeft,
        behavior: "instant",
      });
      // Cached rows can briefly provide enough height before responsive/query
      // reconciliation shrinks them again. Keep restoring through layout changes
      // until the user takes control of this surface.
      if (focusPending && recordFocus) {
        const grid = Array.from(element.querySelectorAll<HTMLElement>('[data-grid-id]')).find(node=>node.dataset.gridId===recordFocus!.grid);
        const row = grid && Array.from(grid.querySelectorAll<HTMLElement>('[data-grid-record-id]')).find(node=>node.dataset.gridRecordId===recordFocus!.id&&node.getClientRects().length);
        const selector = recordFocus.kind === "link" ? 'a[href]' : recordFocus.kind === "preview" ? 'button[title="Preview record"]' : 'button[aria-haspopup="menu"]';
        const target = row?.querySelector<HTMLElement>(selector) ?? row?.querySelector<HTMLElement>('a[href]') ?? row?.querySelector<HTMLElement>('button[aria-label="Record quick actions"]');
        if (target && !target.matches(':disabled') && target.getClientRects().length) {
          target.focus({preventScroll:true});
          focusPending = false;
        }
      }
    };
    const persist = () => {
      if (!form && !pending && navigationViews.isScope(scope))
        navigationViews.save(key, {
          search: location.search,
          scrollTop: position.top,
          scrollLeft: position.left,
          recordFocus,
        });
    };
    const save = () => {
      if (pending) return;
      position = { top: scroll.scrollTop, left: scroll.scrollLeft };
      persist();
    };
    const interact = () => {
      pending = false;
      focusPending = false;
      save();
    };
    const rememberFocus = (event: FocusEvent) => {
      if (!(event.target instanceof HTMLElement)) return;
      const control = event.target.closest<HTMLElement>('a[href],button'), row = control?.closest<HTMLElement>('[data-grid-record-id]'), grid = row?.closest<HTMLElement>('[data-grid-id]');
      if (!control || !row?.dataset.gridRecordId || !grid?.dataset.gridId) return;
      const kind = control.matches('a[href]') ? "link" : control.getAttribute('title') === 'Preview record' ? "preview" : control.getAttribute('aria-haspopup') === 'menu' ? "menu" : undefined;
      if (kind) recordFocus = {grid:grid.dataset.gridId,id:row.dataset.gridRecordId,kind};
    };
    scroll.scrollTo({
      top: restore?.scrollTop || 0,
      left: restore?.scrollLeft || 0,
      behavior: "instant",
    });
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(apply);
    });
    observer.observe(element);
    const focusObserver = new MutationObserver(() => { if (focusPending) apply(); });
    focusObserver.observe(element, {childList:true,subtree:true});
    apply();
    scroll.addEventListener("focusin", rememberFocus);
    scroll.addEventListener("scroll", save, { passive: true });
    scroll.addEventListener("wheel", interact, { passive: true });
    scroll.addEventListener("touchstart", interact, { passive: true });
    scroll.addEventListener("pointerdown", interact, { passive: true });
    scroll.addEventListener("keydown", interact);
    // Only browser-history returns restore a loaded record control. Other routes
    // keep their existing navigation/skip-link focus behavior.
    return () => {
      persist();
      observer.disconnect();
      focusObserver.disconnect();
      cancelAnimationFrame(frame);
      scroll.removeEventListener("scroll", save);
      scroll.removeEventListener("focusin", rememberFocus);
      scroll.removeEventListener("wheel", interact);
      scroll.removeEventListener("touchstart", interact);
      scroll.removeEventListener("pointerdown", interact);
      scroll.removeEventListener("keydown", interact);
    };
  }, [
    scope,
    location.pathname,
    location.search,
    location.hash,
    action,
    navigate,
  ]);
  return (
    <div ref={content} className="suite-route-content" data-route-content>
      <RecordFreshness />
      {children}
    </div>
  );
}
