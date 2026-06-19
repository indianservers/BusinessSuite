import { type ElementType, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  Bell,
  Bot,
  Briefcase,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileSearch,
  Gauge,
  History,
  LayoutDashboard,
  ListChecks,
  MessageSquare,
  Network,
  Package,
  PanelRight,
  Plus,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  TableProperties,
  Target,
  Trophy,
  Users,
  WandSparkles,
  Workflow,
  Zap,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ProgressRing } from "@/components/ui/state";
import { canAccessRoute, getActiveModule } from "@/lib/roles";
import { getProductForContext } from "@/lib/products";
import { useAuthStore } from "@/store/authStore";
import { cn } from "@/lib/utils";
import { getWowFeaturesForContext, type WowFeature } from "@/lib/wowFeatures";

type Density = "compact" | "comfortable" | "spacious";

type RecentItem = {
  path: string;
  label: string;
  module: string;
  visitedAt: number;
};

type ActionItem = {
  label: string;
  path: string;
  icon: ElementType;
  tone?: string;
};

type AuthUser = ReturnType<typeof useAuthStore.getState>["user"];
type CommandAction = ActionItem & { description?: string };

const densityKey = "business-suite-ui-density";
const recentKey = "business-suite-recent-places";
const dismissedSetupKey = "business-suite-dismissed-setup";
const savedViewKey = "business-suite-saved-view";

const densityLabels: Record<Density, string> = {
  compact: "Compact",
  comfortable: "Comfortable",
  spacious: "Spacious",
};

export default function WorkspaceEnhancements() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const product = getProductForContext(location.pathname, user?.role, user?.is_superuser);
  const activeModule = getActiveModule(location.pathname);
  const [open, setOpen] = useState(false);
  const [density, setDensity] = useState<Density>(() => (localStorage.getItem(densityKey) as Density) || "comfortable");
  const [recent, setRecent] = useState<RecentItem[]>(() => readRecent(useAuthStore.getState().user));
  const [savedView, setSavedView] = useState(() => localStorage.getItem(savedViewKey) || "My work");
  const [setupDismissed, setSetupDismissed] = useState(() => localStorage.getItem(dismissedSetupKey) === "true");
  const [command, setCommand] = useState("");

  useEffect(() => {
    document.documentElement.dataset.uiDensity = density;
    localStorage.setItem(densityKey, density);
  }, [density]);

  useEffect(() => {
    const item: RecentItem = {
      path: location.pathname,
      label: readablePath(location.pathname),
      module: product.shortName,
      visitedAt: Date.now(),
    };
    const next = [item, ...readRecent(user).filter((entry) => entry.path !== item.path)].slice(0, 8);
    localStorage.setItem(recentStorageKey(user), JSON.stringify(next));
    setRecent(next);
  }, [location.pathname, product.shortName, user]);

  useEffect(() => {
    localStorage.setItem(savedViewKey, savedView);
  }, [savedView]);

  const quickActions = useMemo(() => filterAllowed(getQuickActions(activeModule), user), [activeModule, user]);
  const attentionItems = useMemo(() => filterAllowed(getAttentionItems(activeModule), user), [activeModule, user]);
  const mobileNav = useMemo(() => filterAllowed(getMobileNav(activeModule), user), [activeModule, user]);
  const wowActions = useMemo(() => filterAllowed(getWowActions(product.key), user), [product.key, user]);
  const commandActions = useMemo(() => filterAllowed(getCommandActions(activeModule, command, product.key), user), [activeModule, command, product.key, user]);
  const setup = getSetupItems(activeModule);
  const setupDone = setup.filter((item) => item.done).length;
  const setupPercent = setup.length ? Math.round((setupDone / setup.length) * 100) : 100;

  const saveCurrentView = () => {
    const label = readablePath(location.pathname);
    setSavedView(label);
  };

  return (
    <>
      {!setupDismissed && activeModule !== "suite" ? (
        <div className="mb-4 rounded-lg border bg-card px-4 py-3 shadow-sm">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex min-w-0 items-center gap-3">
              <ProgressRing value={setupPercent} />
              <div className="min-w-0">
                <p className="text-sm font-semibold">{product.name} readiness</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {setup.slice(0, 5).map((item) => (
                    <Badge key={item.label} variant={item.done ? "default" : "secondary"} className="gap-1">
                      {item.done ? <CheckCircle2 className="h-3 w-3" /> : <Clock className="h-3 w-3" />}
                      {item.label}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
                <PanelRight className="h-4 w-4" />
                Open cockpit
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  localStorage.setItem(dismissedSetupKey, "true");
                  setSetupDismissed(true);
                }}
                aria-label="Dismiss readiness"
                title="Dismiss"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="fixed bottom-4 right-4 z-40 hidden md:block">
        <Button className="h-11 rounded-full shadow-lg" onClick={() => setOpen(true)}>
          <Sparkles className="h-4 w-4" />
          Cockpit
        </Button>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 px-2 py-2 shadow-[0_-8px_24px_rgba(15,23,42,0.08)] backdrop-blur md:hidden">
        <div className="mx-auto grid max-w-md grid-cols-4 gap-1">
          {mobileNav.slice(0, 4).map((item) => (
            <button
              key={item.path}
              className={cn(
                "flex min-h-12 flex-col items-center justify-center rounded-md px-1 text-[10px] font-medium text-muted-foreground",
                location.pathname === item.path && "bg-primary/10 text-primary"
              )}
              onClick={() => navigate(item.path)}
            >
              <item.icon className="mb-1 h-4 w-4" />
              <span className="max-w-full truncate">{item.label}</span>
            </button>
          ))}
        </div>
      </nav>

      {open ? (
        <div className="fixed inset-0 z-50 bg-black/35" onClick={() => setOpen(false)}>
          <aside
            className="ml-auto flex h-full w-full max-w-xl flex-col overflow-hidden border-l bg-background shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          >
            <header className="flex items-center justify-between border-b px-5 py-4">
              <div>
                <p className="text-sm font-semibold">{product.name}</p>
                <p className="text-xs text-muted-foreground">Workspace cockpit</p>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setOpen(false)} aria-label="Close cockpit" title="Close">
                <X className="h-4 w-4" />
              </Button>
            </header>

            <div className="flex-1 overflow-y-auto p-5">
              <section className="rounded-lg border bg-card p-4">
                <div className="mb-3 flex items-center gap-2">
                  <Bot className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold">AI Command Center</h2>
                </div>
                <div className="relative">
                  <WandSparkles className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    value={command}
                    onChange={(event) => setCommand(event.target.value)}
                    className="h-10 w-full rounded-md border bg-background pl-9 pr-3 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/15"
                    placeholder="Try: stale leads, payroll audit, SLA risk, approval flow..."
                  />
                </div>
                <div className="mt-3 grid gap-2">
                  {commandActions.slice(0, 4).map((item) => (
                    <button
                      key={item.path}
                      className="flex items-center justify-between rounded-md border px-3 py-2 text-left text-sm hover:bg-accent"
                      onClick={() => {
                        navigate(item.path);
                        setOpen(false);
                      }}
                    >
                      <span className="flex min-w-0 items-center gap-2">
                        <item.icon className="h-4 w-4 shrink-0 text-primary" />
                        <span className="min-w-0">
                          <span className="block truncate font-medium">{item.label}</span>
                          {item.description ? <span className="block truncate text-xs text-muted-foreground">{item.description}</span> : null}
                        </span>
                      </span>
                      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                    </button>
                  ))}
                </div>
              </section>

              <section className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold">Quick Actions</h2>
                  <Button variant="outline" size="sm" onClick={saveCurrentView}>
                    <Plus className="h-4 w-4" />
                    Save View
                  </Button>
                </div>
                <div className="grid gap-2 sm:grid-cols-2">
                  {quickActions.map((item) => (
                    <Link key={item.path} to={item.path} onClick={() => setOpen(false)} className="group flex items-center gap-3 rounded-lg border bg-card p-3 transition hover:border-primary/40 hover:bg-accent">
                      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-white", item.tone || "bg-primary")}>
                        <item.icon className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1 text-sm font-medium">{item.label}</span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground transition group-hover:translate-x-0.5" />
                    </Link>
                  ))}
                </div>
              </section>

              <section className="mt-6">
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <h2 className="text-sm font-semibold">Wow Features</h2>
                  </div>
                  <Badge variant="secondary">{wowActions.length} active</Badge>
                </div>
                <div className="grid gap-2">
                  {wowActions.map((item) => (
                    <Link key={item.path + item.label} to={item.path} onClick={() => setOpen(false)} className="flex items-center gap-3 rounded-lg border bg-card p-3 hover:bg-accent">
                      <span className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-white", item.tone || "bg-primary")}>
                        <item.icon className="h-4 w-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{item.label}</span>
                        {"description" in item && item.description ? <span className="block truncate text-xs text-muted-foreground">{item.description}</span> : null}
                      </span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  ))}
                </div>
              </section>

              <section className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg border bg-card p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <TableProperties className="h-4 w-4 text-primary" />
                    <h2 className="text-sm font-semibold">Table Density</h2>
                  </div>
                  <div className="grid grid-cols-3 gap-1 rounded-md bg-muted p-1">
                    {(Object.keys(densityLabels) as Density[]).map((option) => (
                      <button
                        key={option}
                        className={cn("rounded px-2 py-1.5 text-xs font-medium", density === option ? "bg-background shadow-sm" : "text-muted-foreground")}
                        onClick={() => setDensity(option)}
                      >
                        {densityLabels[option]}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border bg-card p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <ListChecks className="h-4 w-4 text-primary" />
                    <h2 className="text-sm font-semibold">Saved View</h2>
                  </div>
                  <button className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm hover:bg-muted" onClick={() => navigate(location.pathname)}>
                    <span className="truncate">{savedView}</span>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </button>
                </div>
              </section>

              <section className="mt-6">
                <div className="mb-3 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <h2 className="text-sm font-semibold">Needs Attention</h2>
                </div>
                <div className="space-y-2">
                  {attentionItems.map((item) => (
                    <Link key={item.path} to={item.path} onClick={() => setOpen(false)} className="flex items-center justify-between rounded-lg border bg-card px-3 py-2.5 text-sm hover:bg-accent">
                      <span className="flex items-center gap-2">
                        <item.icon className="h-4 w-4 text-muted-foreground" />
                        {item.label}
                      </span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  ))}
                </div>
              </section>

              <section className="mt-6">
                <div className="mb-3 flex items-center gap-2">
                  <History className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold">Recently Visited</h2>
                </div>
                <div className="space-y-2">
                  {recent.map((item) => (
                    <Link key={item.path} to={item.path} onClick={() => setOpen(false)} className="flex items-center justify-between rounded-lg border bg-card px-3 py-2.5 text-sm hover:bg-accent">
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{item.label}</span>
                        <span className="text-xs text-muted-foreground">{item.module}</span>
                      </span>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  ))}
                </div>
              </section>
            </div>
          </aside>
        </div>
      ) : null}
    </>
  );
}

function filterAllowed<T extends ActionItem>(items: T[], user: AuthUser): T[] {
  return items.filter((item) => canAccessRoute(item.path, user?.role, user?.is_superuser));
}

function recentStorageKey(user: AuthUser) {
  return user?.id ? `${recentKey}:${user.id}` : `${recentKey}:anonymous`;
}

function readRecent(user?: AuthUser): RecentItem[] {
  try {
    const raw = JSON.parse(localStorage.getItem(recentStorageKey(user || null)) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

function readablePath(path: string) {
  const parts = path.split("/").filter(Boolean);
  if (!parts.length) return "Suite Home";
  return parts
    .filter((part, index) => !(index === 0 && ["hrms", "crm", "pms", "srm", "fam"].includes(part.toLowerCase())))
    .map((part) => part.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()))
    .join(" / ") || parts[0].toUpperCase();
}

function getQuickActions(module: string): ActionItem[] {
  if (module === "crm") {
    return [
      { label: "New Lead", path: "/crm/leads", icon: Plus, tone: "bg-emerald-600" },
      { label: "Pipeline", path: "/crm/pipeline", icon: Target, tone: "bg-blue-600" },
      { label: "Support Tickets", path: "/crm/tickets", icon: Bell, tone: "bg-rose-600" },
      { label: "Customer 360", path: "/crm/customer-360", icon: Network, tone: "bg-cyan-700" },
      { label: "Webforms", path: "/crm/webforms", icon: Users, tone: "bg-violet-600" },
      { label: "AI Copilot", path: "/ai/copilot", icon: Sparkles, tone: "bg-slate-700" },
    ];
  }
  if (module === "hrms") {
    return [
      { label: "Employee Directory", path: "/hrms/employees", icon: Users, tone: "bg-blue-600" },
      { label: "Attendance", path: "/hrms/attendance", icon: Clock, tone: "bg-cyan-700" },
      { label: "Leave", path: "/hrms/leave", icon: CalendarDays, tone: "bg-emerald-600" },
      { label: "Payroll", path: "/hrms/payroll", icon: Gauge, tone: "bg-violet-600" },
      { label: "Approvals", path: "/hrms/approval-os", icon: CheckCircle2, tone: "bg-amber-600" },
      { label: "Documents", path: "/hrms/documents", icon: Package, tone: "bg-slate-700" },
    ];
  }
  if (module === "project_management") {
    return [
      { label: "Projects", path: "/pms/projects", icon: Briefcase, tone: "bg-violet-600" },
      { label: "Backlog", path: "/pms/backlog", icon: ListChecks, tone: "bg-blue-600" },
      { label: "Calendar", path: "/pms/calendar", icon: CalendarDays, tone: "bg-cyan-700" },
      { label: "Reports", path: "/pms/reports", icon: Gauge, tone: "bg-emerald-600" },
    ];
  }
  return [
    { label: "Dashboard", path: "/business-os", icon: LayoutDashboard, tone: "bg-blue-600" },
    { label: "Analytics", path: "/analytics", icon: Gauge, tone: "bg-emerald-600" },
    { label: "AI Agents", path: "/ai-agents", icon: Sparkles, tone: "bg-slate-700" },
    { label: "Settings", path: "/admin/business-os/modules", icon: Settings, tone: "bg-violet-600" },
  ];
}

function getCommandActions(module: string, query: string, productKey: string): CommandAction[] {
  const normalized = query.trim().toLowerCase();
  const base: CommandAction[] = [
    { label: "Ask AI Copilot", description: "Open the natural language command workspace", path: "/ai/copilot", icon: Bot, tone: "bg-slate-700" },
    { label: "Build a report", description: "Create report views, forecasts, funnels, and exports", path: "/analytics/report-builder", icon: FileSearch, tone: "bg-blue-600" },
    { label: "Open smart inbox", description: "Review approvals, requests, and exceptions", path: "/workflow", icon: ListChecks, tone: "bg-amber-600" },
    { label: "Launch automation recipes", description: "Start from prebuilt workflow blueprints", path: "/admin/automation/blueprints", icon: Zap, tone: "bg-violet-600" },
  ];
  if (module === "crm" || productKey === "crm") {
    base.unshift(
      { label: "Find stale leads", description: "Prioritize stale CRM leads and follow-ups", path: "/crm/leads", icon: Clock, tone: "bg-emerald-600" },
      { label: "Check SLA risk", description: "Open critical tickets and escalation queues", path: "/crm/tickets", icon: ShieldAlert, tone: "bg-rose-600" },
      { label: "Open Customer 360", description: "View the full customer timeline", path: "/crm/customer-360", icon: Network, tone: "bg-cyan-700" },
    );
  }
  if (module === "hrms" || productKey === "hrms") {
    base.unshift(
      { label: "Run payroll audit", description: "Check LOP, arrears, loans, and statutory flags", path: "/hrms/payroll", icon: Gauge, tone: "bg-violet-600" },
      { label: "Review attendance anomalies", description: "Find missed punches and shift issues", path: "/hrms/attendance", icon: Clock, tone: "bg-cyan-700" },
      { label: "Open Employee 360", description: "Review employee profile and lifecycle details", path: "/hrms/employees", icon: Users, tone: "bg-blue-600" },
    );
  }
  if (!normalized) return base;
  return base.filter((item) => `${item.label} ${item.description || ""}`.toLowerCase().includes(normalized));
}

function getWowActions(productKey: string): CommandAction[] {
  return getWowFeaturesForContext(productKey).map((feature) => ({
    label: feature.title,
    description: feature.subtitle,
    path: feature.path,
    icon: iconForWowFeature(feature),
    tone: toneForImpact(feature.impact),
  }));
}

function iconForWowFeature(feature: WowFeature) {
  if (feature.title.includes("Command") || feature.title.includes("AI")) return Bot;
  if (feature.title.includes("360")) return Network;
  if (feature.title.includes("Inbox") || feature.title.includes("Approval")) return Workflow;
  if (feature.title.includes("WhatsApp")) return MessageSquare;
  if (feature.title.includes("Attendance") || feature.title.includes("Payroll")) return Gauge;
  if (feature.title.includes("Risk") || feature.title.includes("SLA")) return ShieldAlert;
  if (feature.title.includes("Document")) return Package;
  if (feature.title.includes("Gamified")) return Trophy;
  if (feature.title.includes("Mobile")) return Users;
  if (feature.title.includes("Marketplace") || feature.title.includes("Automation")) return Zap;
  return Sparkles;
}

function toneForImpact(impact: WowFeature["impact"]) {
  const tones: Record<WowFeature["impact"], string> = {
    AI: "bg-slate-700",
    Automation: "bg-violet-600",
    Insight: "bg-cyan-700",
    Mobile: "bg-blue-600",
    Workflow: "bg-amber-600",
  };
  return tones[impact];
}

function getAttentionItems(module: string): ActionItem[] {
  if (module === "crm") {
    return [
      { label: "Stale leads", path: "/crm/leads", icon: Clock },
      { label: "Critical tickets", path: "/crm/tickets", icon: AlertTriangle },
      { label: "Quote approvals", path: "/crm/quote-approvals", icon: CheckCircle2 },
      { label: "Follow-ups due", path: "/crm/tasks", icon: Bell },
    ];
  }
  if (module === "hrms") {
    return [
      { label: "Missed punches", path: "/hrms/attendance", icon: Clock },
      { label: "Pending leave", path: "/hrms/leave", icon: CalendarDays },
      { label: "Payroll pre-checks", path: "/hrms/payroll", icon: Gauge },
      { label: "Document expiry", path: "/hrms/documents", icon: AlertTriangle },
    ];
  }
  return [
    { label: "Pending approvals", path: "/business-os", icon: CheckCircle2 },
    { label: "Reports", path: "/analytics", icon: Gauge },
    { label: "Configuration", path: "/admin/business-os/modules", icon: Settings },
  ];
}

function getMobileNav(module: string): ActionItem[] {
  if (module === "crm") {
    return [
      { label: "Home", path: "/crm", icon: LayoutDashboard },
      { label: "Leads", path: "/crm/leads", icon: Users },
      { label: "Deals", path: "/crm/deals", icon: Target },
      { label: "Tickets", path: "/crm/tickets", icon: Bell },
    ];
  }
  if (module === "hrms") {
    return [
      { label: "Home", path: "/hrms", icon: LayoutDashboard },
      { label: "ESS", path: "/hrms/ess", icon: Users },
      { label: "Leave", path: "/hrms/leave", icon: CalendarDays },
      { label: "Payroll", path: "/hrms/payroll", icon: Gauge },
    ];
  }
  return [
    { label: "Home", path: "/", icon: LayoutDashboard },
    { label: "Search", path: "/business-os", icon: Search },
    { label: "Reports", path: "/analytics", icon: Gauge },
    { label: "AI", path: "/ai-agents", icon: Sparkles },
  ];
}

function getSetupItems(module: string) {
  if (module === "crm") {
    return [
      { label: "Lead capture", done: true },
      { label: "Pipeline", done: true },
      { label: "Auto-response", done: true },
      { label: "CSAT", done: true },
      { label: "Reports", done: true },
    ];
  }
  if (module === "hrms") {
    return [
      { label: "Employees", done: true },
      { label: "Attendance", done: true },
      { label: "Leave rules", done: true },
      { label: "Payroll", done: true },
      { label: "Compliance", done: true },
    ];
  }
  return [
    { label: "Modules", done: true },
    { label: "Roles", done: true },
    { label: "Reports", done: true },
  ];
}
