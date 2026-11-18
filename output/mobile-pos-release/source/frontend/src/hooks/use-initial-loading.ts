import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/** Keep mounted content during subsequent reads; retain `loading` for busy controls. */
export function useInitialLoading(loading: boolean) {
  const { pathname } = useLocation();
  const completedPath = useRef<string | null>(null);
  useEffect(() => {
    if (!loading) completedPath.current = pathname;
  }, [loading, pathname]);
  return loading && completedPath.current !== pathname;
}
