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
    const apply = () => {
      if (!pending) return;
      scroll.scrollTo({
        top: restore!.scrollTop,
        left: restore!.scrollLeft,
        behavior: "instant",
      });
      if (scroll.scrollHeight - scroll.clientHeight >= restore!.scrollTop)
        pending = false;
    };
    const save = () => {
      if (!form && !pending && navigationViews.isScope(scope))
        navigationViews.save(key, {
          search: location.search,
          scrollTop: scroll.scrollTop,
          scrollLeft: scroll.scrollLeft,
        });
    };
    const interact = () => {
      pending = false;
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
    apply();
    scroll.addEventListener("scroll", save, { passive: true });
    scroll.addEventListener("wheel", interact, { passive: true });
    scroll.addEventListener("touchstart", interact, { passive: true });
    scroll.addEventListener("pointerdown", interact, { passive: true });
    // Leave focus on the clicked navigation control. Keyboard users can use the existing skip link.
    return () => {
      save();
      observer.disconnect();
      cancelAnimationFrame(frame);
      scroll.removeEventListener("scroll", save);
      scroll.removeEventListener("wheel", interact);
      scroll.removeEventListener("touchstart", interact);
      scroll.removeEventListener("pointerdown", interact);
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
