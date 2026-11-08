import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Layers3, Search, Settings2, Star } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { operationalWorkspaceDefinitions } from "./workspace-domains";
import "./workspace-directory.css";

type Item = { id: string; name: string; href: string };
function readIds(key: string): string[] { try { const data = JSON.parse(localStorage.getItem(key) || "[]"); return Array.isArray(data) ? data.filter(id => typeof id === "string") : []; } catch { return []; } }
export function WorkspaceDirectoryMenu() {
  const user = useAuthStore(s => s.user);
  const location = useLocation();
  const module = location.pathname.split("/")[1];
  const scope = `${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-organization") || ""}:${sessionStorage.getItem("suite-branch") || ""}:${module}`;
  if (!["pms", "crm", "hrms", "srm", "fam"].includes(module) || !canAccessRoute(`/${module}/workspaces`, user?.role, user?.is_superuser)) return null;
  return <ScopedWorkspaceMenu key={scope} module={module as "pms" | "crm" | "hrms" | "srm" | "fam"} scope={scope} />;
}
function ScopedWorkspaceMenu({ module, scope }: { module: "pms" | "crm" | "hrms" | "srm" | "fam"; scope: string }) {
  const user = useAuthStore(s => s.user);
  const location = useLocation();
  const [open, setOpen] = useState(false), [search, setSearch] = useState("");
  const recentKey = `suite:workspace-recents:v1:${scope}`;
  const [recent, setRecent] = useState<string[]>(() => readIds(recentKey));
  const [favorites, setFavorites] = useState<string[]>([]);
  const query = useQuery({ queryKey: ["workspace-directory", "pms", scope.slice(0, -module.length - 1), JSON.stringify([user?.role, user?.is_superuser, user?.access?.grants.project_management])], enabled: open && module === "pms", queryFn: ({ signal }) => api.get<{ id: number; name: string }[]>("/project-management/workspaces", { signal }).then(result => result.data), staleTime: 0 });
  useEffect(() => { setOpen(false); setSearch(""); }, [location.pathname, location.search]);
  const items: Item[] = module === "pms" ? (query.data || []).map(row => ({ id: String(row.id), name: row.name, href: `/pms/workspaces?workspace=${row.id}` })) : operationalWorkspaceDefinitions[module].domains.filter(domain => canAccessRoute(domain.path, user?.role, user?.is_superuser)).map(domain => ({ id: domain.path, name: domain.name, href: domain.path }));
  const selected = query.isError && module === "pms" ? undefined : module === "pms" ? items.find(item => item.id === new URLSearchParams(location.search).get("workspace")) : items.find(item => location.pathname === item.href || location.pathname.startsWith(item.href + "/"));
  function remember(id: string) { const next = [id, ...recent.filter(value => value !== id)].slice(0, 5); setRecent(next); try { localStorage.setItem(recentKey, JSON.stringify(next)); } catch { /* Optional preference. */ } setOpen(false); }
  const label = ({ pms: "Projects", crm: "CRM", hrms: "People", srm: "Sales", fam: "Finance" })[module];
  const filtered = items.filter(item => item.name.toLowerCase().includes(search.trim().toLowerCase()));
  return <Popover open={open} onOpenChange={value => {
    setOpen(value); setSearch("");
    if (value) try { const saved = JSON.parse(localStorage.getItem(`suite:workspace-directory:v1:${scope}`) || "{}"); setFavorites(Array.isArray(saved.favorites) ? saved.favorites.filter((id: unknown) => typeof id === "string") : []); } catch { setFavorites([]); }
  }}><PopoverTrigger asChild><Button variant="outline" size="sm" className="wd-switcher-trigger" aria-label="Open workspace switcher"><Layers3 size={16} /><span>{selected?.name || "Workspaces"}</span><ChevronDown size={13} /></Button></PopoverTrigger><PopoverContent align="end" className="wd-switcher-menu"><div className="wd-switcher-heading"><strong>{label} workspaces</strong><span>Current company & branch</span></div><label className="wd-switcher-search"><Search size={16} /><Input autoFocus aria-label="Search available workspaces" placeholder="Find a workspace…" value={search} onChange={event => setSearch(event.target.value)} /></label>
    {module === "pms" && query.isFetching && <p role="status">Checking workspace access…</p>}
    {module === "pms" && query.isError ? <div role="alert"><p>Workspaces could not load.</p><Button variant="outline" size="sm" onClick={() => void query.refetch()}>Retry</Button></div> : !query.isFetching && <div className="wd-switcher-options">{["Favorites", "Recent", "All workspaces"].map(group => {
      const rows = filtered.filter(item => group === "Favorites" ? favorites.includes(item.id) : group === "Recent" ? recent.includes(item.id) && !favorites.includes(item.id) : !favorites.includes(item.id) && !recent.includes(item.id));
      if (group === "Recent") rows.sort((a, b) => recent.indexOf(a.id) - recent.indexOf(b.id));
      return rows.length > 0 && <section key={group}><h2>{group}</h2>{rows.map(item => <Link key={item.id} to={item.href} aria-current={selected?.id === item.id ? "page" : undefined} onClick={() => remember(item.id)}><Layers3 size={17} /><span>{item.name}<small>{label}</small></span>{favorites.includes(item.id) && <Star size={13} />}</Link>)}</section>;
    })}{!filtered.length && <p>No available workspaces match your search.</p>}</div>}
    <Link className="wd-switcher-manage" to={`/${module}/workspaces`} onClick={() => setOpen(false)}><Settings2 size={16} />Manage workspaces</Link>
  </PopoverContent></Popover>;
}
