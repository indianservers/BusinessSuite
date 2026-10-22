import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  BriefcaseBusiness,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  Code2,
  Download,
  FileStack,
  FileText,
  Filter,
  GitBranch,
  Keyboard,
  Layers3,
  Link2,
  ListChecks,
  LockKeyhole,
  MoreHorizontal,
  Network,
  Pencil,
  Play,
  Rocket,
  Save,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Timer,
  Users,
  Workflow,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  adminSchemes,
  automationRules,
  blueprintFlows,
  budgetForecast,
  calculateGoalProgress,
  calculateReportDepth,
  commentsThreads,
  defaultSavedViews,
  detectDependencyWarnings,
  enterpriseGoals,
  enterpriseIssues,
  enterpriseReleases,
  enterpriseSprints,
  fileVersions,
  intakeForms,
  invoiceDrafts,
  notificationPreferences,
  recalculatePlan,
  resourceAllocations,
  runKQL,
  timesheetApprovals,
  wikiPages,
  workflowDefinitions,
  type EnterpriseIssue,
  type SavedView,
} from "../enterpriseEngine";

const sections = [
  { id: "plans", label: "Advanced Plans", icon: Network },
  { id: "navigator", label: "Issue Navigator", icon: Search },
  { id: "goals", label: "Goals", icon: Target },
  { id: "backlog", label: "Backlog & Sprints", icon: ListChecks },
  { id: "workflows", label: "Workflows", icon: Workflow },
  { id: "automation", label: "Automation", icon: Zap },
  { id: "dependencies", label: "Dependencies", icon: Link2 },
  { id: "releases", label: "Releases", icon: Rocket },
  { id: "reports", label: "Reports", icon: BarChart3 },
  { id: "business", label: "Business Ops", icon: BriefcaseBusiness },
  { id: "collab", label: "Collaboration", icon: BookOpen },
  { id: "admin", label: "Enterprise Admin", icon: ShieldCheck },
  { id: "agile", label: "Agile Software", icon: Code2 },
  { id: "ux", label: "UX Power Tools", icon: Keyboard },
];

export default function EnterpriseEnginePage() {
  const [activeSection, setActiveSection] = useState("plans");
  const [issues, setIssues] = useState<EnterpriseIssue[]>(() => {
    const stored = localStorage.getItem("karyaflow-enterprise-issues");
    return stored ? JSON.parse(stored) : enterpriseIssues;
  });
  const [queryText, setQueryText] = useState(defaultSavedViews[0].query);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [sprints, setSprints] = useState(() => enterpriseSprints);
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => {
    const stored = localStorage.getItem("pms-saved-views");
    return stored ? JSON.parse(stored) : defaultSavedViews;
  });
  const [scenarioDelay, setScenarioDelay] = useState(4);
  const [compactMode, setCompactMode] = useState(false);

  useEffect(() => {
    localStorage.setItem("karyaflow-enterprise-issues", JSON.stringify(issues));
  }, [issues]);

  useEffect(() => {
    localStorage.setItem("pms-saved-views", JSON.stringify(savedViews));
  }, [savedViews]);

  const filteredIssues = useMemo(() => runKQL(queryText, issues), [issues, queryText]);
  const reports = calculateReportDepth(issues);
  const warnings = detectDependencyWarnings(issues);
  const delayedPlan = recalculatePlan("KAR-103", scenarioDelay, issues);
  const selectedIssues = issues.filter((issue) => selectedIds.includes(issue.id));

  const saveCurrentView = () => {
    const next: SavedView = {
      id: `view-${Date.now()}`,
      name: `Saved view ${savedViews.length + 1}`,
      query: queryText,
      columns: ["key", "summary", "status", "assignee", "storyPoints"],
      subscription: "Weekly",
    };
    setSavedViews((items) => [next, ...items]);
  };

  const bulkMoveToSprint = () => {
    setIssues((items) => items.map((issue) => selectedIds.includes(issue.id) ? { ...issue, sprint: "Sprint 24", status: issue.status === "Backlog" ? "Selected" : issue.status } : issue));
    setQueryText("sprint = Sprint 24 AND status != Done");
    setSelectedIds([]);
  };

  const updateIssue = (id: number, patch: Partial<EnterpriseIssue>) => {
    setIssues((items) => items.map((issue) => issue.id === id ? { ...issue, ...patch } : issue));
  };

  const bulkAssignToMe = () => {
    setIssues((items) => items.map((issue) => selectedIds.includes(issue.id) ? { ...issue, assignee: "Current User" } : issue));
  };

  const bulkArchive = () => {
    setIssues((items) => items.filter((issue) => !selectedIds.includes(issue.id)));
    setSelectedIds([]);
  };

  const exportCsv = () => {
    const headers = ["key", "summary", "type", "status", "priority", "assignee", "sprint", "fixVersion", "storyPoints"];
    const rows = filteredIssues.map((issue) => headers.map((key) => JSON.stringify(String(issue[key as keyof EnterpriseIssue] ?? ""))).join(","));
    const blob = new Blob([[headers.join(","), ...rows].join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "karyaflow-work-export.csv";
    link.click();
    URL.revokeObjectURL(url);
  };

  const runAiPlanner = () => {
    const nextId = Math.max(...issues.map((issue) => issue.id)) + 1;
    const nextRank = Math.max(...issues.map((issue) => issue.rank)) + 1;
    setIssues((items) => [
      {
        ...enterpriseIssues[0],
        id: nextId,
        key: `KAR-${100 + nextId}`,
        type: "Task",
        summary: "AI suggested: reduce dependency risk before release",
        status: "Backlog",
        priority: "High",
        assignee: "Maya Nair",
        reporter: "Current User",
        storyPoints: 5,
        sprint: "Backlog",
        epic: "Planning",
        release: "v2.4",
        dueDate: "2026-06-06",
        initiative: "Planning",
        component: "Timeline",
        fixVersion: "v2.4",
        originalEstimate: 30,
        remainingEstimate: 30,
        plannedStart: "2026-05-28",
        plannedEnd: "2026-06-06",
        rank: nextRank,
        security: "Internal",
        development: { commits: 0, prs: 0, deployments: 0, build: "Pending" },
      },
      ...items,
    ]);
    setQueryText("priority = High AND status != Done");
    setActiveSection("navigator");
  };

  const updateSprintStatus = (id: string, status: string) => {
    setSprints((items) => items.map((sprint) => sprint.id === id ? { ...sprint, status } : sprint));
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div role="status" className="border-b border-amber-200 bg-amber-50 px-5 py-3 text-sm text-amber-900">Prototype — local sample data. Use <a className="underline font-semibold" href="/pms/workspaces">Workspaces</a> for shared tasks, invitations, calendar and workload.</div>
      <div className="border-b bg-white px-5 py-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-blue-700">
              <Sparkles className="h-4 w-4" />
              PMS Enterprise Engine
            </div>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">KaryaFlow enterprise project operations</h1>
            <p className="mt-1 text-sm text-muted-foreground">Prototype lab for exploring planning and governance concepts with sample data. Changes here are saved in this browser and are not shared production records.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => setCompactMode((value) => !value)}><Layers3 className="h-4 w-4" />{compactMode ? "Comfortable" : "Compact"} cards</Button>
            <Button variant="outline" size="sm" onClick={exportCsv}><Download className="h-4 w-4" />Export CSV</Button>
            <Button size="sm" onClick={runAiPlanner}><Bot className="h-4 w-4" />Run planning simulation</Button>
          </div>
        </div>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {sections.map((section) => (
            <button
              key={section.id}
              type="button"
              onClick={() => setActiveSection(section.id)}
              className={`inline-flex shrink-0 items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium ${activeSection === section.id ? "border-blue-600 bg-blue-50 text-blue-700" : "bg-white text-slate-600 hover:bg-slate-50"}`}
            >
              <section.icon className="h-4 w-4" />
              {section.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-5 p-5 xl:grid-cols-[18rem_1fr]">
        <aside className="space-y-4">
          <MetricCard icon={Network} label="Plan warnings" value={warnings.filter((warning) => warning.critical).length.toString()} danger />
          <MetricCard icon={Target} label="Goal rollups" value={`${enterpriseGoals.length} active`} />
          <MetricCard icon={Rocket} label="Release readiness" value={`${enterpriseReleases[1].readiness}%`} />
          <MetricCard icon={Timer} label="Timesheets" value={`${timesheetApprovals.length} pending flow`} />
          <Card>
            <CardContent className="p-4">
              <h2 className="font-semibold">Saved views</h2>
              <div className="mt-3 space-y-2">
                {savedViews.slice(0, 5).map((view) => (
                  <button key={view.id} type="button" onClick={() => setQueryText(view.query)} className="w-full rounded-md border bg-white p-2 text-left text-sm hover:border-blue-300">
                    <span className="font-medium">{view.name}</span>
                    <span className="mt-1 block truncate text-xs text-muted-foreground">{view.query}</span>
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        </aside>

        <main className="space-y-5">
          {activeSection === "plans" ? (
            <SectionCard title="Real Advanced Roadmaps / Plans" icon={Network} action={<Button size="sm" onClick={() => setScenarioDelay((value) => value + 1)}>Delay scenario +1 day</Button>}>
              <div className="grid gap-4 xl:grid-cols-[1fr_20rem]">
                <div className="overflow-x-auto rounded-lg border">
                  <div className="min-w-[760px] bg-white">
                    {delayedPlan.map((issue) => (
                      <div key={issue.key} className="grid grid-cols-[8rem_1fr_9rem_9rem_8rem] items-center border-b px-4 py-3 text-sm last:border-b-0">
                        <span className="font-semibold text-blue-700">{issue.key}</span>
                        <span>{issue.summary}</span>
                        <span>{issue.assignee}</span>
                        <span>{issue.plannedStart}</span>
                        <Badge variant="outline">{issue.release}</Badge>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <InfoRow label="Capacity model" value={`${resourceAllocations.filter((item) => item.utilization > 90).length} people over 90%`} />
                  <InfoRow label="Scenario delay" value={`${scenarioDelay} days after KAR-103`} />
                  <InfoRow label="Release alignment" value={`${enterpriseReleases.filter((release) => release.launchDateShared).length} shared launch dates`} />
                  <InfoRow label="Schedule recalculation" value="Dependents shifted automatically" />
                </div>
              </div>
            </SectionCard>
          ) : null}

          {activeSection === "navigator" ? (
            <SectionCard title="Full Issue Navigator" icon={Search} action={<Button size="sm" onClick={saveCurrentView}><Save className="h-4 w-4" />Save view</Button>}>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input value={queryText} onChange={(event) => setQueryText(event.target.value)} className="pl-9 font-mono" />
                </div>
                <Button variant="outline"><Filter className="h-4 w-4" />Advanced filters</Button>
                <Button variant="outline"><Bell className="h-4 w-4" />Subscribe</Button>
              </div>
              <BulkBar count={selectedIds.length} onMove={bulkMoveToSprint} onAssign={bulkAssignToMe} onArchive={bulkArchive} />
              <IssueTable issues={filteredIssues} selectedIds={selectedIds} setSelectedIds={setSelectedIds} compact={compactMode} onUpdate={updateIssue} />
            </SectionCard>
          ) : null}

          {activeSection === "goals" ? (
            <SectionCard title="Real Goal Progress Engine" icon={Target}>
              <div className="grid gap-3 md:grid-cols-3">
                {enterpriseGoals.map((goal) => {
                  const progress = calculateGoalProgress(goal, issues);
                  return (
                    <div key={goal.id} className="rounded-lg border bg-white p-4">
                      <Badge className={progress.status === "On track" ? "bg-emerald-100 text-emerald-800 hover:bg-emerald-100" : progress.status === "At risk" ? "bg-amber-100 text-amber-800 hover:bg-amber-100" : "bg-red-100 text-red-800 hover:bg-red-100"}>{progress.status}</Badge>
                      <h3 className="mt-3 font-semibold">{goal.name}</h3>
                      <div className="mt-3 h-2 rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${progress.progress}%` }} /></div>
                      <p className="mt-2 text-sm text-muted-foreground">{progress.progress}% from {progress.linked.length} linked issues, milestones, and {goal.release}</p>
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          ) : null}

          {activeSection === "backlog" ? (
            <SectionCard title="Backlog Grooming + Sprint Lifecycle" icon={ListChecks}>
              <div className="grid gap-4 xl:grid-cols-[1fr_20rem]">
                <div className="space-y-2">
                  {[...issues].sort((a, b) => a.rank - b.rank).map((issue) => (
                    <div key={issue.key} className="grid grid-cols-[3rem_6rem_1fr_8rem_7rem] items-center rounded-md border bg-white px-3 py-2 text-sm">
                      <span className="font-semibold text-slate-500">#{issue.rank}</span>
                      <span className="font-semibold text-blue-700">{issue.key}</span>
                      <span>{issue.summary}</span>
                      <Badge variant="outline">{issue.epic}</Badge>
                      <span className={issue.storyPoints ? "text-slate-700" : "text-red-600"}>{issue.storyPoints || "Missing"} pts</span>
                    </div>
                  ))}
                </div>
                <div className="space-y-3">
                  {sprints.map((sprint) => (
                    <div key={sprint.id} className="rounded-lg border bg-white p-4">
                      <div className="flex items-center justify-between">
                        <h3 className="font-semibold">{sprint.name}</h3>
                        <Badge>{sprint.status}</Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">{sprint.goal}</p>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                        <InfoRow label="Committed" value={`${sprint.committedPoints} pts`} />
                        <InfoRow label="Completed" value={`${sprint.completedPoints} pts`} />
                        <InfoRow label="Scope changes" value={`${sprint.scopeChanges}`} />
                        <InfoRow label="Carry-over" value={sprint.carriedOver.join(", ") || "None"} />
                      </div>
                      <div className="mt-3 flex gap-2"><Button size="sm" onClick={() => updateSprintStatus(sprint.id, "Active")}><Play className="h-4 w-4" />Start</Button><Button size="sm" variant="outline" onClick={() => updateSprintStatus(sprint.id, "Completed")}>Complete</Button></div>
                    </div>
                  ))}
                </div>
              </div>
            </SectionCard>
          ) : null}

          {activeSection === "workflows" ? <DataGrid title="Custom Workflows" icon={Workflow} rows={workflowDefinitions.map((item) => [item.workType, item.statuses.join(" -> "), item.validators.join(", "), item.postFunctions.join(", "), item.approvals.join(", ")])} /> : null}
          {activeSection === "automation" ? <DataGrid title="Automation Engine + Blueprint Automation" icon={Zap} rows={[...automationRules.map((item) => [item.name, item.trigger, item.condition, item.action, item.active ? "Active" : "Paused"]), ...blueprintFlows.map((item) => [item.name, item.stages.join(" -> "), item.owner, item.sla, "Blueprint"])]} /> : null}
          {activeSection === "dependencies" ? <DataGrid title="Dependency Engine" icon={Link2} rows={warnings.map((item) => [typeof item.from === "string" ? item.from : item.from?.key || "Unknown", typeof item.to === "string" ? item.to : item.to?.key || "Unknown", item.type, item.warning, item.critical ? "Critical path" : "Normal"])} /> : null}
          {activeSection === "releases" ? <DataGrid title="Release Management" icon={Rocket} rows={enterpriseReleases.map((item) => [item.name, item.status, `${item.readiness}% ready`, item.fixVersions.join(", "), item.notes])} /> : null}
          {activeSection === "reports" ? <DataGrid title="Reports Depth" icon={BarChart3} rows={Object.entries(reports).map(([name, value]) => [name, value, "Calculated", "Export ready", "Dashboard widget"])} /> : null}
          {activeSection === "business" ? <BusinessOps /> : null}
          {activeSection === "collab" ? <CollaborationOps /> : null}
          {activeSection === "admin" ? <DataGrid title="Admin / Enterprise" icon={ShieldCheck} rows={adminSchemes.map((item) => [item.type, item.name, item.controls, "Configured", "Audited"])} /> : null}
          {activeSection === "agile" ? <AgileSoftware issues={issues} /> : null}
          {activeSection === "ux" ? <UxPowerTools selectedCount={selectedIssues.length} /> : null}
        </main>
      </div>
    </div>
  );
}

function IssueTable({ issues, selectedIds, setSelectedIds, compact, onUpdate }: { issues: EnterpriseIssue[]; selectedIds: number[]; setSelectedIds: (ids: number[]) => void; compact: boolean; onUpdate: (id: number, patch: Partial<EnterpriseIssue>) => void }) {
  return (
    <div className="mt-4 overflow-x-auto rounded-lg border bg-white">
      <table className="w-full min-w-[980px] text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-muted-foreground">
          <tr><th className="p-3">Select</th><th>Key</th><th>Summary</th><th>Status</th><th>Assignee</th><th>Fix version</th><th>Security</th><th>Inline edit</th></tr>
        </thead>
        <tbody>
          {issues.map((issue) => (
            <tr key={issue.key} className="border-t">
              <td className="p-3"><input type="checkbox" checked={selectedIds.includes(issue.id)} onChange={(event) => setSelectedIds(event.target.checked ? [...selectedIds, issue.id] : selectedIds.filter((id) => id !== issue.id))} /></td>
              <td className="font-semibold text-blue-700">{issue.key}</td>
              <td className={compact ? "py-2" : "py-4"}>{issue.summary}</td>
              <td><select value={issue.status} onChange={(event) => onUpdate(issue.id, { status: event.target.value as EnterpriseIssue["status"] })} className="rounded border px-2 py-1"><option>Backlog</option><option>Selected</option><option>In Progress</option><option>In Review</option><option>Done</option></select></td>
              <td><select value={issue.assignee} onChange={(event) => onUpdate(issue.id, { assignee: event.target.value })} className="rounded border px-2 py-1"><option>{issue.assignee}</option><option>Current User</option><option>Maya Nair</option><option>Dev Patel</option><option>Isha Rao</option><option>Nora Khan</option><option>Rahul Shah</option></select></td>
              <td><Input value={issue.fixVersion || ""} onChange={(event) => onUpdate(issue.id, { fixVersion: event.target.value })} className="h-8 w-24" /></td>
              <td><Badge variant="outline">{issue.security}</Badge></td>
              <td><Button variant="ghost" size="sm"><Pencil className="h-4 w-4" />Edit</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BulkBar({ count, onMove, onAssign, onArchive }: { count: number; onMove: () => void; onAssign: () => void; onArchive: () => void }) {
  if (!count) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg border bg-blue-50 p-3 text-sm">
      <span className="font-semibold text-blue-900">{count} selected</span>
      <Button size="sm" onClick={onMove}>Move to Sprint 24</Button>
      <Button size="sm" variant="outline" onClick={onAssign}>Bulk assign</Button>
      <Button size="sm" variant="outline">Update priority</Button>
      <Button size="sm" variant="outline" onClick={onArchive}>Archive</Button>
    </div>
  );
}

function BusinessOps() {
  return (
    <SectionCard title="Business Operations" icon={BriefcaseBusiness}>
      <div className="grid gap-4 xl:grid-cols-3">
        <MiniTable title="Budget Forecasting" rows={[["Planned", money(budgetForecast.planned)], ["Actual", money(budgetForecast.actual)], ["Forecast", money(budgetForecast.forecastAtCompletion)], ["Margin", `${Math.round(budgetForecast.margin * 100)}%`]]} />
        <MiniTable title="Timesheet Approvals" rows={timesheetApprovals.map((item) => [item.user, `${item.hours}h / ${item.billable} billable`, item.status])} />
        <MiniTable title="Invoice Drafts" rows={invoiceDrafts.map((item) => [item.id, item.client, money(item.amount)])} />
        <MiniTable title="Resource Utilization" rows={resourceAllocations.map((item) => [item.name, `${item.utilization}%`, item.holidays ? `${item.holidays} holiday` : "Available"])} />
      </div>
    </SectionCard>
  );
}

function CollaborationOps() {
  return (
    <SectionCard title="Collaboration Systems" icon={BookOpen}>
      <div className="grid gap-4 xl:grid-cols-2">
        <MiniTable title="Real Comment Threads" rows={commentsThreads.map((item) => [item.issue, item.visibility, `${item.replies} replies, ${item.edits} edits${item.pinned ? ", pinned" : ""}`])} />
        <MiniTable title="Pages / Wiki" rows={wikiPages.map((item) => [item.title, item.type, item.linked])} />
        <MiniTable title="Forms / Intake Builder" rows={intakeForms.map((item) => [item.name, item.routesTo, `Creates ${item.creates}`])} />
        <MiniTable title="File Versioning" rows={fileVersions.map((item) => [item.file, `${item.versions} versions`, `${item.preview}, ${item.virusScan}`])} />
        <MiniTable title="Notification Preferences" rows={notificationPreferences.map((item) => [item.event, item.inApp ? "In-app" : "Off", item.email ? "Email" : item.digest ? "Digest" : "Muted"])} />
      </div>
    </SectionCard>
  );
}

function AgileSoftware({ issues }: { issues: EnterpriseIssue[] }) {
  return (
    <SectionCard title="Agile / Software Delivery" icon={Code2}>
      <div className="grid gap-4 xl:grid-cols-2">
        <MiniTable title="Hierarchy and Rollups" rows={enterpriseGoals.map((goal) => {
          const rollup = calculateGoalProgress(goal, issues);
          return [goal.name, `${rollup.progress}%`, `${rollup.linked.reduce((sum, issue) => sum + issue.storyPoints, 0)} pts`];
        })} />
        <MiniTable title="Development Panel" rows={issues.map((issue) => [issue.key, issue.development.branch || "No branch", `${issue.development.commits} commits / ${issue.development.prs} PRs / ${issue.development.build}`])} />
        <MiniTable title="Component Ownership" rows={issues.map((issue) => [issue.component, issue.assignee, issue.key])} />
        <MiniTable title="Bug Tracking Fields" rows={issues.filter((issue) => issue.type === "Bug").map((issue) => [issue.key, `${issue.severity} ${issue.environment}`, `${issue.affectedVersion} -> ${issue.fixVersion}${issue.regression ? " regression" : ""}`])} />
      </div>
    </SectionCard>
  );
}

function UxPowerTools({ selectedCount }: { selectedCount: number }) {
  return (
    <SectionCard title="Mobile / UX Power Tools" icon={Keyboard}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {[
          ["Responsive board polish", "Horizontal lanes, compact cards, drawer detail editing, touch-ready controls"],
          ["Inline editing", "Status, assignee, dates, priority, estimates editable in tables"],
          ["Bulk actions", `${selectedCount} selected now, with assign/status/sprint/archive/export actions`],
          ["Keyboard shortcuts", "C to create, / to search, A assign to me, M move status, ? help"],
          ["Saved views", "Persisted per browser now; ready for user/team/project backend persistence"],
          ["Command palette", "Global create/search/navigation pattern ready for integration"],
        ].map(([title, detail]) => (
          <div key={title} className="rounded-lg border bg-white p-4">
            <h3 className="font-semibold">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

function DataGrid({ title, icon, rows }: { title: string; icon: React.ElementType; rows: string[][] }) {
  return (
    <SectionCard title={title} icon={icon}>
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full min-w-[760px] text-left text-sm">
          <tbody>
            {rows.map((row) => (
              <tr key={row.join("-")} className="border-b last:border-b-0">
                {row.map((cell, index) => <td key={index} className={index === 0 ? "p-3 font-semibold text-slate-900" : "p-3 text-muted-foreground"}>{cell}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function SectionCard({ title, icon: Icon, action, children }: { title: string; icon: React.ElementType; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <h2 className="flex items-center gap-2 text-lg font-semibold"><Icon className="h-5 w-5 text-blue-700" />{title}</h2>
          <div className="flex gap-2">{action}<Button variant="ghost" size="icon"><MoreHorizontal className="h-4 w-4" /></Button></div>
        </div>
        {children}
      </CardContent>
    </Card>
  );
}

function MetricCard({ icon: Icon, label, value, danger = false }: { icon: React.ElementType; label: string; value: string; danger?: boolean }) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <Icon className={danger ? "h-5 w-5 text-red-600" : "h-5 w-5 text-blue-700"} />
          {danger ? <AlertTriangle className="h-4 w-4 text-red-600" /> : <CheckCircle2 className="h-4 w-4 text-emerald-600" />}
        </div>
        <p className="mt-3 text-sm text-muted-foreground">{label}</p>
        <p className="mt-1 text-xl font-semibold">{value}</p>
      </CardContent>
    </Card>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return <div className="rounded-md border bg-white p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>;
}

function MiniTable({ title, rows }: { title: string; rows: string[][] }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <h3 className="font-semibold">{title}</h3>
      <div className="mt-3 space-y-2">
        {rows.map((row) => (
          <div key={row.join("-")} className="rounded-md bg-slate-50 p-2 text-sm">
            <p className="font-medium">{row[0]}</p>
            <p className="text-xs text-muted-foreground">{row.slice(1).join(" | ")}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function money(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value);
}

