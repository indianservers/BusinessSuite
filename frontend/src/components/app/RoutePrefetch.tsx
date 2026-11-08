import { Children, isValidElement, useEffect } from "react";
import { matchRoutes } from "react-router-dom";
import type { FrontendRoute } from "@/appRegistry";
import { canAccessRoute } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";

type Preload = () => Promise<unknown>;
let active = 0;
const done = new Set<string>(),
  budget: number[] = [];
function loaders(element: unknown): Preload[] {
  if (!isValidElement<{ children?: React.ReactNode }>(element)) return [];
  const type = element.type as { preload?: Preload };
  return [
    ...(typeof type.preload === "function" ? [type.preload] : []),
    ...Children.toArray(element.props.children).flatMap(loaders),
  ];
}
/** Code-only intent prefetch. No records, forms, permissions, or hidden pages are mounted. */
export default function RoutePrefetch({ routes }: { routes: FrontendRoute[] }) {
  useEffect(() => {
    let stopped = false;
    const queued = new Map<string, ReturnType<typeof setTimeout>>();
    const connection = () =>
      (
        navigator as Navigator & {
          connection?: { saveData?: boolean; effectiveType?: string };
        }
      ).connection;
    const allowedNetwork = () => {
      const info = connection();
      const memory = (navigator as Navigator & { deviceMemory?: number })
        .deviceMemory;
      return (
        !info?.saveData &&
        !/^(slow-)?2g$/.test(info?.effectiveType || "") &&
        (!memory || memory > 1)
      );
    };
    const anchor = (target: EventTarget | null) =>
      target instanceof Element
        ? target.closest<HTMLAnchorElement>("a[href]")
        : null;
    const href = (link: HTMLAnchorElement | null) => {
      if (
        !link ||
        link.download ||
        (link.target && link.target !== "_self") ||
        link.rel.split(/\s+/).includes("external")
      )
        return;
      const url = new URL(link.href, location.href);
      if (url.origin !== location.origin || !/^https?:$/.test(url.protocol))
        return;
      const user = useAuthStore.getState().user;
      if (!user || !canAccessRoute(url.pathname, user.role, user.is_superuser))
        return;
      return url.pathname;
    };
    const intent = (event: Event) => {
      const path = href(anchor(event.target));
      if (
        !path ||
        stopped ||
        queued.has(path) ||
        !allowedNetwork() ||
        document.visibilityState === "hidden"
      )
        return;
      const matches = matchRoutes(routes, path);
      const route = matches?.[matches.length - 1]?.route;
      const key = route?.path;
      if (!key || done.has(key)) return;
      const candidates = loaders(route.element);
      if (!candidates.length) return;
      const timer = setTimeout(
        () => {
          queued.delete(path);
          const now = Date.now();
          while (budget.length && budget[0] < now - 60000) budget.shift();
          if (stopped || active >= 2 || budget.length >= 4 || !allowedNetwork())
            return;
          active++;
          budget.push(now);
          done.add(key);
          while (done.size > 200) done.delete(done.values().next().value!);
          void Promise.all(candidates.map((load) => load()))
            .catch(() => done.delete(key))
            .finally(() => {
              active--;
            });
        },
        event.type === "focusin" ? 0 : 90,
      );
      queued.set(path, timer);
    };
    const leave = (event: Event) => {
      const link = anchor(event.target);
      if (
        event instanceof MouseEvent &&
        link?.contains(event.relatedTarget as Node | null)
      )
        return;
      const path = href(link);
      if (path) {
        clearTimeout(queued.get(path));
        queued.delete(path);
      }
    };
    document.addEventListener("pointerover", intent);
    document.addEventListener("focusin", intent);
    document.addEventListener("pointerout", leave);
    document.addEventListener("focusout", leave);
    return () => {
      stopped = true;
      queued.forEach(clearTimeout);
      document.removeEventListener("pointerover", intent);
      document.removeEventListener("focusin", intent);
      document.removeEventListener("pointerout", leave);
      document.removeEventListener("focusout", leave);
    };
  }, [routes]);
  return null;
}
