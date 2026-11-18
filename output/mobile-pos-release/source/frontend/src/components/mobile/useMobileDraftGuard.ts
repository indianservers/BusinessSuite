import { useCallback, useEffect, useLayoutEffect, useRef } from "react";

type DraftGuard = {
  enabled: boolean;
  dirty: boolean;
  draftKey: string;
  pending: () => boolean;
  onDiscard: () => void;
  message: string;
  confirmDiscard?: (confirm: () => void) => void;
  guardHistory?: boolean;
};

/** Link/unload guard with opt-in indexed browser history protection. */
export function useMobileDraftGuard(options: DraftGuard) {
  const latest = useRef(options);
  const accepted = useRef<string | null>(null);
  const historyIndex=useRef<number|undefined>();
  const restoring=useRef<{index:number;delta:number}|null>(null);
  useLayoutEffect(()=>{if(!restoring.current){const index=window.history.state?.idx;historyIndex.current=Number.isInteger(index)?index:undefined;}});
  latest.current = options;
  if (!options.dirty) accepted.current = null;
  const requestLeave = useCallback((afterDiscard?:()=>void) => {
    const current = latest.current;
    if (!current.enabled) return true;
    if (current.pending()) return false;
    if (!current.dirty || accepted.current === current.draftKey) return true;
    if(current.confirmDiscard){
      current.confirmDiscard(()=>{const confirmed=latest.current;if(confirmed.pending())return;accepted.current=confirmed.draftKey;confirmed.onDiscard();afterDiscard?.();});
      return false;
    }
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
      if (!requestLeave(()=>link.click())) { event.preventDefault(); event.stopPropagation(); }
    };
    const pop=(event:PopStateEvent)=>{
      const target=event.state?.idx;
      const current=latest.current;
      if(!current.guardHistory||!Number.isInteger(target))return;
      if(restoring.current){
        // Restore the original entry before asking; React Router must keep the editor mounted.
        event.stopImmediatePropagation();
        const restore=restoring.current;
        if(target!==restore.index){window.history.go(restore.index-target);return;}
        restoring.current=null;
        const proceed=()=>window.history.go(restore.delta);
        if(requestLeave(proceed))proceed();
        return;
      }
      if(!current.enabled||!current.pending()&&(!current.dirty||accepted.current===current.draftKey))return;
      const index=historyIndex.current;
      if(index===undefined||target===index)return;
      event.stopImmediatePropagation();
      restoring.current={index,delta:target-index};
      window.history.go(index-target);
    };
    window.addEventListener("beforeunload", unload);
    if(options.guardHistory)window.addEventListener("popstate",pop,true);
    document.addEventListener("click", click, true);
    return () => {
      window.removeEventListener("beforeunload", unload);
      window.removeEventListener("popstate",pop,true);
      document.removeEventListener("click", click, true);
    };
  }, [options.enabled,options.guardHistory, requestLeave]);
  return requestLeave;
}
