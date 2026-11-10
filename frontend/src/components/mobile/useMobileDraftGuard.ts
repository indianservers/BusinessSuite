import { useCallback, useEffect, useRef } from "react";

type DraftGuard = {
  enabled: boolean;
  dirty: boolean;
  draftKey: string;
  pending: () => boolean;
  onDiscard: () => void;
  message: string;
};

/** Phone link/unload guard; callers own values, save completion and route actions. */
export function useMobileDraftGuard(options: DraftGuard) {
  const latest = useRef(options);
  const accepted = useRef<string | null>(null);
  latest.current = options;
  if (!options.dirty) accepted.current = null;
  const requestLeave = useCallback(() => {
    const current = latest.current;
    if (!current.enabled) return true;
    if (current.pending()) return false;
    if (!current.dirty || accepted.current === current.draftKey) return true;
    if (!window.confirm(current.message)) return false;
    // Prevent a second native prompt while React commits the accepted discard.
    accepted.current = current.draftKey;
    current.onDiscard();
    return true;
  }, []);
  useEffect(() => {
    if (!options.enabled) return;
    const unload = (event: BeforeUnloadEvent) => {
      const current = latest.current;
      if (!current.enabled) return;
      if (current.pending() || current.dirty && accepted.current !== current.draftKey) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    const click = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const link = (event.target as Element)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || link.hasAttribute("download") || link.target && link.target !== "_self") return;
      const next = new URL(link.href, location.href);
      if (!["http:", "https:"].includes(next.protocol)) return;
      if (next.origin === location.origin && next.pathname === location.pathname && next.search === location.search) return;
      if (!requestLeave()) { event.preventDefault(); event.stopPropagation(); }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", click, true);
    };
  }, [options.enabled, requestLeave]);
  return requestLeave;
}
