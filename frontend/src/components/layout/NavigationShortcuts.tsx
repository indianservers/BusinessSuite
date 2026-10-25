import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Clock3, TrendingUp } from "lucide-react";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute, getRoleNav } from "@/lib/roles";

type SavedPage = { path: string; label: string };
type NavigationHistory = { recent: SavedPage[]; visits: Record<string, number> };
const emptyHistory = (): NavigationHistory => ({ recent: [], visits: {} });

export default function NavigationShortcuts({ excludedPaths = [], collapsed = false, onNavigate }: {
  excludedPaths?: string[];
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const { pathname } = useLocation();
  const user = useAuthStore((s) => s.user);
  const key = `kf-navigation-${user?.id || 0}`;
  const lastVisit = useRef("");
  const [saved, setSaved] = useState<NavigationHistory>(emptyHistory);
  const menu = getRoleNav(user?.role, user?.is_superuser, pathname);
  const modulePrefix = `/${pathname.split("/")[1]}`;

  useEffect(() => {
    const visitKey = `${key}:${pathname}`;
    if (lastVisit.current === visitKey) return;
    lastVisit.current = visitKey;
    let previous: Record<string, unknown> = {};
    try { previous = JSON.parse(localStorage.getItem(key) || "{}") || {}; } catch { /* Start with clean history. */ }
    const recent = Array.isArray(previous.recent) ? previous.recent.filter((page): page is SavedPage =>
      typeof page?.path === "string" && typeof page?.label === "string") : [];
    const visits: Record<string, number> = {};
    if (previous.visits && typeof previous.visits === "object") {
      for (const [path, count] of Object.entries(previous.visits)) {
        if (typeof count === "number" && Number.isFinite(count) && count > 0) visits[path] = count;
      }
    }
    const page = getRoleNav(user?.role, user?.is_superuser, pathname).find(item => item.to === pathname);
    const next = { recent, visits };
    if (page) {
      next.recent = [{ path: pathname, label: page.label }, ...recent.filter(item => item.path !== pathname)].slice(0, 100);
      next.visits = { ...visits, [pathname]: (visits[pathname] || 0) + 1 };
    }
    setSaved(next);
    try { localStorage.setItem(key, JSON.stringify({ ...previous, ...next })); } catch { /* Navigation works without storage. */ }
  }, [key, pathname, user?.role, user?.is_superuser]);

  const available = menu.filter(item => item.to.startsWith(`${modulePrefix}/`) &&
    !excludedPaths.includes(item.to) && canAccessRoute(item.to, user?.role, user?.is_superuser));
  const byPath = new Map(available.map(item => [item.to, item]));
  const recent = saved.recent.filter((page, index, pages) => byPath.has(page.path) &&
    pages.findIndex(item => item.path === page.path) === index).slice(0, 5)
    .map(page => ({ path: page.path, label: byPath.get(page.path)!.label }));
  const top = [...new Map(available.map(item => [item.to, item])).values()]
    .filter(item => saved.visits[item.to] > 0)
    .sort((a, b) => saved.visits[b.to] - saved.visits[a.to] ||
      saved.recent.findIndex(page => page.path === a.to) - saved.recent.findIndex(page => page.path === b.to))
    .slice(0, 5).map(item => ({ path: item.to, label: item.label }));
  if (!top.length && !recent.length) return null;
  return <div className={`kf-shortcuts kf-menu-history${collapsed ? " kf-menu-history-collapsed" : ""}`}>
    {[{ title: "Top 5", icon: TrendingUp, pages: top }, { title: "Recent 5", icon: Clock3, pages: recent }]
      .filter(section => section.pages.length > 0).map(({ title, icon: Icon, pages }) =>
        <section key={title} aria-label={title}>
          {!collapsed && <p className="kf-menu-history-heading">{title}</p>}
          {pages.map(page => <Link key={page.path} to={page.path} title={`${title}: ${page.label}`}
            aria-label={`${title}: ${page.label}`} onClick={onNavigate} aria-current={pathname === page.path ? "page" : undefined}>
            <Icon size={14} />{!collapsed && <span>{page.label}</span>}
          </Link>)}
        </section>)}
  </div>;
}
