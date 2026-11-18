import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Layers3, Search, Settings2, Star } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { canAccessRoute } from "@/lib/roles";
import { switchSuiteContext } from "@/lib/switch-suite-context";
import { useWorkspaceContext } from "./useWorkspaceContext";
import { workspaceApiBase, workspaceDataScope, workspaceSelectionKey, type SavedWorkspace } from "./workspace-management-types";
import "./workspace-directory.css";

type Module = "pms" | "crm" | "hrms" | "srm" | "fam";
type NavigationWorkspace = Pick<SavedWorkspace, "id" | "name" | "status"> & { key?: string; module?: Module; company_id?: number; company_name?: string; branch_id?: number | null; branch_name?: string };
type Item = { id: string; ref: string; name: string; href: string; company?: number; branch?: number | null; subtitle?: string };
function readIds(key: string): string[] { try { const data = JSON.parse(localStorage.getItem(key) || "[]"); return Array.isArray(data) ? data.filter(id => typeof id === "string") : []; } catch { return []; } }
export function WorkspaceDirectoryMenu() {
  const user = useAuthStore(s => s.user);
  const location = useLocation();
  const module = location.pathname.split("/")[1];
  const context = useWorkspaceContext(["pms", "crm", "hrms", "srm", "fam"].includes(module));
  const scope = `${user?.id}:${user?.access?.companyId}:${sessionStorage.getItem("suite-organization") || ""}:${sessionStorage.getItem("suite-branch") || ""}:${module}`;
  if (!context.ready || !["pms", "crm", "hrms", "srm", "fam"].includes(module) || !canAccessRoute(`/${module}/workspaces`, user?.role, user?.is_superuser)) return null;
  return <ScopedWorkspaceMenu key={scope} module={module as "pms" | "crm" | "hrms" | "srm" | "fam"} scope={scope} />;
}
function ScopedWorkspaceMenu({ module, scope }: { module: "pms" | "crm" | "hrms" | "srm" | "fam"; scope: string }) {
  const user = useAuthStore(s => s.user);
  const location = useLocation();
  const [open, setOpen] = useState(false), [search, setSearch] = useState("");
  const qc = useQueryClient();
  const admin = Boolean(user?.is_superuser || user?.access?.isAccessAdmin);
  const [navigationError, setNavigationError] = useState("");
  const recentKey = `suite:workspace-recents:v1:${scope}`;
  const [recent, setRecent] = useState<string[]>(() => readIds(recentKey));
  const [favorites, setFavorites] = useState<string[]>([]);
  const selectionKey = workspaceSelectionKey(user, module);
  let remembered: string | null = null;
  try { remembered = localStorage.getItem(selectionKey); } catch { /* Optional preference. */ }
  const explicitRef = new URLSearchParams(location.search).get("space") || (module === "pms" ? new URLSearchParams(location.search).get("workspace") : null);
  const currentRef = explicitRef || (location.pathname !== `/${module}/workspaces` && remembered && /^[0-9a-f]{1,64}$/.test(remembered) ? remembered : null);
  const dataScope = workspaceDataScope(user);
  const query = useQuery({ queryKey: [admin ? "admin-workspace-navigation" : "managed-workspaces", module, dataScope], enabled: open || Boolean(currentRef), queryFn: ({ signal }) => api.get<{ items: NavigationWorkspace[] }>(admin ? "/branches/workspaces" : workspaceApiBase(module), { signal }).then(result => result.data), staleTime: 0, retry: false });
  const refetch = query.refetch;
  useEffect(() => { if (currentRef) void refetch({ cancelRefetch: false }); }, [currentRef, location.pathname, refetch]);
  useEffect(() => { setOpen(false); setSearch(""); }, [location.pathname, location.search]);
  const items: Item[] = (query.data?.items || []).filter(row => admin || row.status === "Active").map(row => ({ id: row.key || row.id, ref: row.id,
    name: row.name + (row.status === "Archived" ? " (archived)" : ""), href: `/${row.module || module}/workspaces?space=${encodeURIComponent(row.id)}`,
    company: row.company_id, branch: row.branch_id, subtitle: row.company_name ? `${row.company_name} · ${(row.module || module).toUpperCase()} · ${row.branch_name}` : undefined }));
  const selected = query.isError || !explicitRef && query.isFetching ? undefined : items.find(item => item.ref === currentRef && (!item.company || item.company === user?.access?.companyId));
  async function openWorkspace(item: Item) {
    setNavigationError("");
    try { await switchSuiteContext(qc, item.company!, String(item.branch ?? "all"), item.href); }
    catch { setNavigationError("Could not open that workspace. Your current company and branch have been preserved."); }
  }
  function remember(id: string) { const next = [id, ...recent.filter(value => value !== id)].slice(0, 5); setRecent(next); try { localStorage.setItem(recentKey, JSON.stringify(next)); } catch { /* Optional preference. */ } setOpen(false); }
  const label = ({ pms: "Projects", crm: "CRM", hrms: "People", srm: "Sales", fam: "Finance" })[module];
  const filtered = items.filter(item => `${item.name} ${item.subtitle || ""}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <Popover open={open} onOpenChange={value => {
    setOpen(value); setSearch("");
    if (value) try { const saved = JSON.parse(localStorage.getItem(`suite:workspace-directory:v1:${scope}`) || "{}"); setFavorites(Array.isArray(saved.favorites) ? saved.favorites.filter((id: unknown) => typeof id === "string") : []); } catch { setFavorites([]); }
  }}><PopoverTrigger asChild><Button variant="outline" size="sm" className="wd-switcher-trigger" aria-label="Open workspace switcher"><Layers3 size={16} /><span>{selected?.name || "Workspaces"}</span><ChevronDown size={13} /></Button></PopoverTrigger><PopoverContent align="end" className="wd-switcher-menu"><div className="wd-switcher-heading"><strong>{admin ? "Company workspaces" : `${label} workspaces`}</strong><span>{user?.is_superuser ? "All companies & branches" : admin ? "All branches in your company" : "Current company & branch"}</span></div><label className="wd-switcher-search"><Search size={16} /><Input autoFocus aria-label="Search available workspaces" placeholder="Find a workspace…" value={search} onChange={event => setSearch(event.target.value)} /></label>
    {navigationError && <p role="alert">{navigationError}</p>}
    {query.isFetching && <p role="status">Checking workspace access…</p>}
    {query.isError ? <div role="alert"><p>Workspaces could not load.</p><Button variant="outline" size="sm" onClick={() => void query.refetch()}>Retry</Button></div> : !query.isFetching && <div className="wd-switcher-options">{["Favorites", "Recent", "All workspaces"].map(group => {
      const rows = filtered.filter(item => group === "Favorites" ? favorites.includes(item.id) : group === "Recent" ? recent.includes(item.id) && !favorites.includes(item.id) : !favorites.includes(item.id) && !recent.includes(item.id));
      if (group === "Recent") rows.sort((a, b) => recent.indexOf(a.id) - recent.indexOf(b.id));
      return rows.length > 0 && <section key={group}><h2>{group}</h2>{rows.map(item => <Link key={item.id} to={item.href} aria-current={selected?.id === item.id ? "page" : undefined} onClick={event => { if (admin && item.company) { event.preventDefault(); void openWorkspace(item); } else remember(item.id); }}><Layers3 size={17} /><span>{item.name}<small>{item.subtitle || label}</small></span>{favorites.includes(item.id) && <Star size={13} />}</Link>)}</section>;
    })}{!filtered.length && <p>No available workspaces match your search.</p>}</div>}
    <Link className="wd-switcher-manage" to={`/${module}/workspaces`} onClick={() => setOpen(false)}><Settings2 size={16} />Manage workspaces</Link>
  </PopoverContent></Popover>;
}
