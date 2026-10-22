import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

export function useNewRecordFocus() {
  const location = useLocation();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (location.hash !== "#new-record") return;
    ref.current?.scrollIntoView({ block: "start" });
    ref.current?.querySelector<HTMLInputElement>("input:not([disabled]), textarea, select")?.focus({ preventScroll: true });
  }, [location.key, location.hash]);
  return ref;
}
