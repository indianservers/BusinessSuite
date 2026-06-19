import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock,
  DollarSign,
  GitBranch,
  Link2,
  ListChecks,
  Network,
  ShieldCheck,
  Target,
  TrendingDown,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatCurrency } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import {
  WorkIssues,
  teamMembers,
  workAdvancedPlanning,
  workGoals,
  workReleases,
  workReports,
} from "../workData";

type PMSOpsMode = "dependencies" | "resources" | "agile" | "financials" | "risk";

const pageMeta: Record<PMSOpsMode, { title: string; description: string; action: string; actionPath: string }> = {
  dependencies: {
    title: "Dependency Management",
    description: "Blockers, critical path, cross-project dependencies, and delivery impact analysis.",
    action: "Add dependency",
    actionPath: "/pms/timeline-plus",
  },
  resources: {
    title: "Resource Planning",
    description: "Workload, availability, capacity, skill matching, and over-allocation warnings.",
    action: "Rebalance workload",
    actionPath: "/pms/workload",
  },
  agile: {
    title: "Agile Execution",
    description: "Backlog grooming, sprint planning, velocity, burndown, and release confidence.",
    action: "Plan sprint",
    actionPath: "/pms/sprints",
  },
  financials: {
    title: "Project Financials",
    description: "Budget, cost tracking, billable hours, margin, and client billing readiness.",
    action: "Review billing",
    actionPath: "/pms/reports",
  },
  risk: {
    title: "Risk & Decision Register",
    description: "Risks, assumptions, decisions, issues, mitigation owners, and escalation tracking.",
    action: "Log risk",
    actionPath: "/pms/risks",
  },
};

export default function PMSOperationsPage({ mode }: { mode: PMSOpsMode }) {
  const navigate = useNavigate();
  const meta = pageMeta[mode];
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="page-title">{meta.title}</h1>
          <p className="page-description">{meta.description}</p>
        </div>
        <Button onClick={() => navigate(meta.actionPath)}>{meta.action}</Button>
      </div>

      {mode === "dependencies" ? <DependencyManagement /> : null}
      {mode === "resources" ? <ResourcePlanning /> : null}
      {mode === "agile" ? <AgileExecution /> : null}
      {mode === "financials" ? <ProjectFinancials /> : null}
      {mode === "risk" ? <RiskRegister /> : null}
    </div>
  );
}

function DependencyManagement() {
  const blockers = WorkIssues.filter((item) => item.priority === "Critical" || item.summary.toLowerCase().includes("blocked"));
  const dependencyRows = [
    ["KAR-104", "KAR-103", "Finish-to-start", "Critical path", "v2.4 slips 4 days if unresolved"],
    ["KAR-106", "KAR-101", "Blocks release", "High", "Automation depends on approval workflow"],
    ["KAR-107", "Calendar Reliability", "Cross-project", "Critical path", "QA capacity impacts release confidence"],
    ["Reports Redesign", "Data Export", "External dependency", "Watch", "Client reporting waits for export validation"],
  ];
  return (
    <>
      <div className="grid gap-3 md:grid-cols-4">
        <Metric icon={AlertTriangle} label="Open blockers" value={blockers.length} tone="red" />
        <Metric icon={GitBranch} label="Critical path items" value="3" tone="amber" />
        <Metric icon={Network} label="Cross-project links" value="8" tone="blue" />
        <Metric icon={TrendingDown} label="Impact if ignored" value="4 days" tone="red" />
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
        <DataCard
          title="Dependency Map"
          rows={dependencyRows}
          headers={["Work", "Depends On", "Type", "Signal", "Impact"]}
        />
        <Card>
          <CardHeader><CardTitle className="text-base">Impact Analysis</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {workAdvancedPlanning.map((item) => (
              <div key={item.plan} className="rounded-lg border p-3">
                <p className="font-medium">{item.plan}</p>
                <p className="mt-1 text-sm text-muted-foreground">{item.signal}</p>
                <Badge className="mt-2" variant="outline">{item.action}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function ResourcePlanning() {
  const rows = teamMembers.map((member, index) => {
    const assigned = member.capacity - 3 + index * 3;
    const load = Math.round((assigned / member.capacity) * 100);
    return [member.name, member.role, `${member.capacity}h`, `${assigned}h`, `${load}%`, load > 100 ? "Over allocated" : load > 90 ? "Watch" : "Available"];
  });
  return (
    <>
      <div className="grid gap-3 md:grid-cols-5">
        <Metric icon={Users} label="People planned" value={teamMembers.length} tone="blue" />
        <Metric icon={Clock} label="Capacity" value={`${teamMembers.reduce((sum, item) => sum + item.capacity, 0)}h`} tone="emerald" />
        <Metric icon={AlertTriangle} label="Over allocations" value={rows.filter((row) => row[5] === "Over allocated").length} tone="red" />
        <Metric icon={Zap} label="Skill matches" value="14" tone="violet" />
        <Metric icon={CheckCircle2} label="Available backups" value="3" tone="emerald" />
      </div>
      <DataCard title="Workload & Capacity" rows={rows} headers={["Member", "Role", "Capacity", "Assigned", "Load", "Signal"]} />
      <div className="grid gap-3 md:grid-cols-3">
        {["Move 5 story points from Maya Nair to Rahul Shah.", "Assign QA reviewer backup for Calendar Reliability.", "Match Dev Patel to API automation blockers this sprint."].map((item) => (
          <Card key={item}><CardContent className="p-4 text-sm">{item}</CardContent></Card>
        ))}
      </div>
    </>
  );
}

function AgileExecution() {
  const sprintScope = WorkIssues.filter((issue) => issue.sprint === "Sprint 24");
  const totalPoints = sprintScope.reduce((sum, issue) => sum + issue.storyPoints, 0);
  const donePoints = sprintScope.filter((issue) => issue.status === "Done").reduce((sum, issue) => sum + issue.storyPoints, 0);
  const confidence = Math.max(0, Math.round(((totalPoints - donePoints - 6) / totalPoints) * 100));
  const rows = WorkIssues.map((issue) => [issue.key, issue.summary, issue.status, `${issue.storyPoints} pts`, issue.sprint, issue.release]);
  return (
    <>
      <div className="grid gap-3 md:grid-cols-5">
        <Metric icon={ListChecks} label="Sprint scope" value={`${totalPoints} pts`} tone="blue" />
        <Metric icon={CheckCircle2} label="Done" value={`${donePoints} pts`} tone="emerald" />
        <Metric icon={TrendingUp} label="Velocity" value="31 pts" tone="violet" />
        <Metric icon={BarChart3} label="Burndown" value={`${totalPoints - donePoints} pts`} tone="amber" />
        <Metric icon={ShieldCheck} label="Release confidence" value={`${confidence}%`} tone="emerald" />
      </div>
      <DataCard title="Backlog Grooming & Sprint Planning" rows={rows} headers={["Key", "Summary", "Status", "Estimate", "Sprint", "Release"]} />
      <div className="grid gap-4 md:grid-cols-3">
        {workReports.slice(0, 3).map((report) => (
          <Card key={report.name}>
            <CardContent className="p-4">
              <p className="font-medium">{report.name}</p>
              <p className="mt-2 text-2xl font-semibold">{report.metric}</p>
              <Badge className="mt-2" variant="outline">{report.status}</Badge>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}

function ProjectFinancials() {
  const financialRows = [
    ["Client Portal Upgrade", 3200000, 1840000, 1210000, "38%", "Ready"],
    ["Calendar Reliability", 1800000, 1420000, 280000, "16%", "Review"],
    ["Reports Redesign", 2400000, 980000, 860000, "36%", "Ready"],
    ["Automation Rules", 1600000, 1220000, 190000, "12%", "Blocked"],
  ] as const;
  const totalBudget = financialRows.reduce((sum, row) => sum + row[1], 0);
  const totalCost = financialRows.reduce((sum, row) => sum + row[2], 0);
  const billable = financialRows.reduce((sum, row) => sum + row[3], 0);
  return (
    <>
      <div className="grid gap-3 md:grid-cols-5">
        <Metric icon={DollarSign} label="Budget" value={formatCurrency(totalBudget)} tone="blue" />
        <Metric icon={TrendingDown} label="Cost" value={formatCurrency(totalCost)} tone="amber" />
        <Metric icon={Clock} label="Billable hours" value="1,248h" tone="emerald" />
        <Metric icon={TrendingUp} label="Margin" value="31%" tone="violet" />
        <Metric icon={CheckCircle2} label="Billing ready" value={formatCurrency(billable)} tone="emerald" />
      </div>
      <DataCard
        title="Budget, Cost & Billing Readiness"
        rows={financialRows.map((row) => [row[0], formatCurrency(row[1]), formatCurrency(row[2]), formatCurrency(row[3]), row[4], row[5]])}
        headers={["Project", "Budget", "Cost", "Billable", "Margin", "Billing"]}
      />
    </>
  );
}

function RiskRegister() {
  const rows = [
    ["Risk", "Calendar QA bottleneck", "Nora Khan", "Add reviewer", "Escalated"],
    ["Assumption", "Client approves milestone flow by May 20", "Maya Nair", "Confirm in steering call", "Watch"],
    ["Decision", "Defer custom PDF styling", "Rahul Shah", "Move to v2.4", "Accepted"],
    ["Issue", "Critical bug blocks dependency map", "Dev Patel", "Fix before sprint close", "Critical"],
    ["Risk", "Billing readiness waits for timesheet cleanup", "Isha Rao", "Lock billable hours", "Open"],
  ];
  return (
    <>
      <div className="grid gap-3 md:grid-cols-5">
        <Metric icon={AlertTriangle} label="Risks" value={rows.filter((row) => row[0] === "Risk").length} tone="red" />
        <Metric icon={Target} label="Assumptions" value={rows.filter((row) => row[0] === "Assumption").length} tone="blue" />
        <Metric icon={CheckCircle2} label="Decisions" value={rows.filter((row) => row[0] === "Decision").length} tone="emerald" />
        <Metric icon={ListChecks} label="Issues" value={rows.filter((row) => row[0] === "Issue").length} tone="amber" />
        <Metric icon={ShieldCheck} label="Escalations" value="2" tone="violet" />
      </div>
      <DataCard title="RAID Register" rows={rows} headers={["Type", "Item", "Owner", "Mitigation", "Status"]} />
      <Card>
        <CardHeader><CardTitle className="text-base">Linked Delivery Goals</CardTitle></CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {workGoals.map((goal) => (
            <div key={goal.goal} className="rounded-lg border p-4">
              <p className="font-medium">{goal.goal}</p>
              <p className="mt-1 text-sm text-muted-foreground">{goal.owner} / {goal.target}</p>
              <Badge className="mt-3" variant={goal.status === "At Risk" ? "destructive" : "outline"}>{goal.status}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </>
  );
}

function Metric({ icon: Icon, label, value, tone }: { icon: React.ElementType; label: string; value: string | number; tone: "blue" | "emerald" | "violet" | "amber" | "red" }) {
  const tones = {
    blue: "bg-blue-100 text-blue-700",
    emerald: "bg-emerald-100 text-emerald-700",
    violet: "bg-violet-100 text-violet-700",
    amber: "bg-amber-100 text-amber-700",
    red: "bg-red-100 text-red-700",
  };
  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <div className={`rounded-lg p-2 ${tones[tone]}`}><Icon className="h-5 w-5" /></div>
        <div>
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-xl font-semibold">{value}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function DataCard({ title, rows, headers }: { title: string; rows: Array<Array<string | number>>; headers: string[] }) {
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{title}</CardTitle></CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full min-w-[860px] text-sm">
          <thead className="bg-muted/60 text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>{headers.map((header) => <th key={header} className="px-4 py-3">{header}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-t">
                {row.map((cell, cellIndex) => (
                  <td key={`${index}-${cellIndex}`} className="px-4 py-3">
                    {cellIndex === row.length - 1 ? <Badge variant="outline">{cell}</Badge> : cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
