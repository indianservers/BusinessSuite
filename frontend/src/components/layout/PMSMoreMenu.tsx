import { useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Link, useLocation } from "react-router-dom";
import { ArrowUpRight, Grid2X2, MoreHorizontal, Search, X } from "lucide-react";
import { canAccessRoute, getRoleNav } from "@/lib/roles";
import { useAuthStore } from "@/store/authStore";
import "./PMSMoreMenu.css";

// Keep aliases searchable through the existing navigation labels; only show one link per URL.
const additionalPages = [
  ["Create project", "/pms/projects/new", "Work & delivery"],
  ["OpenAI settings", "/pms/settings/ai/openai", "Manage & customize"],
  ["Gemini settings", "/pms/settings/ai/gemini", "Manage & customize"],
  ["Claude settings", "/pms/settings/ai/claude", "Manage & customize"],
  ["Overview", "/pms/overview", "Insights"],
  ["Portfolio", "/pms/portfolio", "Insights"],
  ["Timesheets", "/pms/timesheets", "People & collaboration"],
  ["Teams", "/pms/teams", "People & collaboration"],
  ["Messages", "/pms/messages", "People & collaboration"],
  ["Docs", "/pms/docs", "People & collaboration"],
  ["Workload", "/pms/workload", "Planning"],
  ["Custom fields", "/pms/custom-fields", "Manage & customize"],
  ["Task types", "/pms/task-types", "Manage & customize"],
  ["Tags", "/pms/tags", "Manage & customize"],
  ["Workspace reset & restore", "/pms/admin/workspaces", "Manage & customize"],
  ["Backup & recovery", "/pms/recovery", "Manage & customize"],
  ["Trash", "/pms/trash", "Manage & customize"],
  ["AI Operator", "/pms/operator", "Work & delivery"],
  ["Workspace tools", "/pms/workspace-tools", "Work & delivery"],
  ["My profile", "/pms/profile", "Manage & customize"],
] as const;

export default function PMSMoreMenu({
  workspaceId,
  projectId,
  className = "ws-rail-item",
  collapsed = false,
}: {
  workspaceId?: number;
  projectId?: number;
  className?: string;
  collapsed?: boolean;
}) {
  const { user } = useAuthStore();
  const location = useLocation();
  const searchRef = useRef<HTMLInputElement>(null);
  workspaceId =
    workspaceId ||
    Number(new URLSearchParams(location.search).get("workspace")) ||
    undefined;
  projectId =
    projectId ||
    Number(location.pathname.match(/^\/pms\/projects\/(\d+)/)?.[1]) ||
    undefined;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All features");
  const items = useMemo(() => {
    const nav = getRoleNav(user?.role, user?.is_superuser, "/pms").filter((i) =>
      i.to.startsWith("/pms"),
    );
    const group = (s?: string) =>
      s === "Project Planning"
        ? "Planning"
        : s === "Project Admin"
          ? "Manage & customize"
          : s === "Project Collaboration"
            ? "People & collaboration"
            : "Work & delivery";
    const pages = nav.map((i) => ({
      label: i.label,
      to: i.to,
      group: group(i.group),
      icon: i.icon,
    }));
    for (const [label, to, section] of additionalPages)
      if (!pages.some((p) => p.to === to))
        pages.push({ label, to, group: section, icon: Grid2X2 });
    if (projectId)
      for (const [suffix, label] of [
        ["", "Project dashboard"],
        ["board", "Project board"],
        ["gantt", "Project Gantt"],
        ["milestones", "Milestones"],
        ["files", "Project files"],
        ["reports", "Project reports"],
        ["risks", "Project risks"],
        ["analytics", "Project analytics"],
      ])
        pages.push({
          label,
          to: `/pms/projects/${projectId}${suffix ? `/${suffix}` : ""}`,
          group: "Current project",
          icon: Grid2X2,
        });
    const seen = new Set<string>();
    return pages.filter((i) => {
      if (
        seen.has(i.to) ||
        !canAccessRoute(i.to, user?.role, user?.is_superuser)
      )
        return false;
      seen.add(i.to);
      return true;
    });
  }, [user?.role, user?.is_superuser, projectId]);
  const categories = ["All features", ...new Set(items.map((i) => i.group))];
  const matches = items.filter(
    (i) =>
      (category === "All features" || i.group === category) &&
      `${i.label} ${i.group} ${i.to}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
  );
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        if (value) {
          setQuery("");
          setCategory("All features");
        }
      }}
    >
      <Dialog.Trigger asChild>
        <button
          className={className}
          aria-label="More features"
          title="More features"
        >
          <MoreHorizontal size={20} />
          {!collapsed && <span>More</span>}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="pms-more-overlay" />
        <Dialog.Content
          className="pms-more-dialog"
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            searchRef.current?.focus();
          }}
        >
          <header>
            <div>
              <Dialog.Title>Explore KaryaFlow</Dialog.Title>
              <Dialog.Description>
                All your tools, one place. Choose a feature to get started.
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="pms-more-close"
              aria-label="Close More features"
            >
              <X size={20} />
            </Dialog.Close>
          </header>
          <label className="pms-more-search">
            <Search size={18} />
            <input
              ref={searchRef}
              aria-label="Search all PMS features"
              placeholder="Search features, tools, and settings…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button
                aria-label="Clear feature search"
                onClick={() => setQuery("")}
              >
                <X size={16} />
              </button>
            )}
          </label>
          <div className="pms-more-body">
            <nav aria-label="Feature categories">
              {categories.map((c) => (
                <button
                  key={c}
                  aria-pressed={category === c}
                  onClick={() => setCategory(c)}
                >
                  {c}
                  <span>
                    {c === "All features"
                      ? items.length
                      : items.filter((i) => i.group === c).length}
                  </span>
                </button>
              ))}
            </nav>
            <div className="pms-more-results">
              <p role="status">
                {matches.length} {matches.length === 1 ? "feature" : "features"}
                {query ? ` matching “${query}”` : " available"}
              </p>
              {!matches.length && (
                <div className="pms-more-empty">
                  No matching features. Try another search or choose All
                  features.
                </div>
              )}
              {categories.slice(1).map((c) => {
                const section = matches.filter((i) => i.group === c);
                return (
                  section.length > 0 && (
                    <section key={c}>
                      <h3>{c}</h3>
                      <div className="pms-more-grid">
                        {section.map((i) => (
                          <Link
                            key={i.to}
                            to={`${i.to}${workspaceId ? `?workspace=${workspaceId}` : ""}`}
                            onClick={() => setOpen(false)}
                            aria-current={
                              location.pathname === i.to ? "page" : undefined
                            }
                          >
                            <span className="pms-more-icon">
                              <i.icon size={20} />
                            </span>
                            <span>
                              <strong>{i.label}</strong>
                              <small>
                                {i.to.replace("/pms/", "").replace(/-/g, " ")}
                              </small>
                            </span>
                            <ArrowUpRight size={15} />
                          </Link>
                        ))}
                      </div>
                    </section>
                  )
                );
              })}
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
