import { useCallback, useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

export function useNewRecordFocus() {
  const location = useLocation();
  const ref = useRef<HTMLDivElement | null>(null);
  const focus = useCallback((node: HTMLDivElement | null) => {
    if (location.hash !== "#new-record" || !node) return;
    node.scrollIntoView({ block: "start" });
    node.querySelector<HTMLElement>("input:not([disabled]), textarea:not([disabled]), select:not([disabled])")?.focus({ preventScroll: true });
  }, [location.key, location.hash]);
  // Callback refs also handle forms mounted after asynchronous capability checks.
  const attach = useCallback((node: HTMLDivElement | null) => { ref.current = node; focus(node); }, [focus]);
  useEffect(() => focus(ref.current), [focus]);
  return attach;
}
