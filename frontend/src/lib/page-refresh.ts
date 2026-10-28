import { useEffect, useRef, useSyncExternalStore, type DependencyList, type EffectCallback } from "react";
import type { QueryClient } from "@tanstack/react-query";

type Handler = () => void | Promise<unknown>;
const handlers = new Set<Handler>();
const listeners = new Set<() => void>();
type RefreshRun = { pending: number; failed: boolean; changed: number };
let current: RefreshRun | undefined;
let running: Promise<void> | undefined;

export function usePageRefresh(handler: Handler) {
  const latest = useRef(handler);
  latest.current = handler;
  useEffect(() => {
    const refresh = () => latest.current();
    handlers.add(refresh);
    return () => { handlers.delete(refresh); };
  }, []);
}

/** Re-run only a read effect; keep the component, filters and local UI state. */
export function useRefreshableEffect(effect: EffectCallback, dependencies?: DependencyList) {
  const latest = useRef(effect);
  latest.current = effect;
  useEffect(() => {
    let cleanup = effect();
    const refresh = () => {
      if (typeof cleanup === "function") cleanup();
      cleanup = latest.current();
    };
    handlers.add(refresh);
    return () => {
      handlers.delete(refresh);
      if (typeof cleanup === "function") cleanup();
    };
  }, dependencies);
}

/** Called by the API client for GETs started during a manual refresh. */
export function trackPageRefreshRead() {
  const run = current;
  if (!run) return undefined;
  run.pending += 1;
  run.changed = Date.now();
  let finished = false;
  return (success = true) => {
    if (finished) return;
    finished = true;
    run.pending -= 1;
    run.failed ||= !success;
    run.changed = Date.now();
  };
}

export function usePageRefreshing() {
  return useSyncExternalStore(callback => {
    listeners.add(callback);
    return () => { listeners.delete(callback); };
  }, () => Boolean(running));
}

export function refreshPageData(client: QueryClient): Promise<void> {
  if (running) return running;
  const run: RefreshRun = { pending: 0, failed: false, changed: Date.now() };
  current = run;
  running = (async () => {
    const results = await Promise.allSettled([
      ...Array.from(handlers, handler => Promise.resolve().then(handler)),
      client.refetchQueries({ type: "active" }, { throwOnError: true }),
    ]);
    run.failed ||= results.some(result => result.status === "rejected");
    // Let dependent effects enqueue their reads, then wait for network completion.
    const started = Date.now();
    do {
      await new Promise(resolve => setTimeout(resolve, 60));
      if (Date.now() - started > 65000) throw new Error("Refresh is taking longer than expected. Check your connection and try again.");
    } while (run.pending > 0 || Date.now() - run.changed < 250);
    if (run.failed) throw new Error("Some data could not be refreshed. Review the page errors and try again.");
  })().finally(() => {
    current = undefined;
    running = undefined;
    listeners.forEach(callback => callback());
  });
  listeners.forEach(callback => callback());
  return running;
}
