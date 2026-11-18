import GridTable from "@/shared/data-grid/GridTable";
import { NativeSelect } from "@/components/ui/native-select";
import { recordPreviewProps } from "@/components/RecordQuickPreview";
import { useMemo, useState } from "react";
import {
  ArrowRight,
  Columns3,
  Download,
  Filter,
  GripVertical,
  Import,
  Layers3,
  ListChecks,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { exportRows } from "@/lib/export";

type ProductKey = "crm" | "hrms" | "pms";

type WorkflowItem = {
  area: string;
  change: string;
  owner: string;
  status: "Live" | "Ready" | "Configured";
  path: string;
};

type SummaryTile = [label: string, value: number, Icon: LucideIcon];

const commonChanges: WorkflowItem[] = [
  { area: "Access", change: "Dashboard opens directly after login", owner: "Platform", status: "Live", path: "" },
  { area: "Branding", change: "Dedicated product theme and shell", owner: "Design", status: "Live", path: "" },
  { area: "Navigation", change: "Left sidebar shows this product only", owner: "Platform", status: "Live", path: "" },
  { area: "Security", change: "Role-based menu visibility", owner: "Security", status: "Live", path: "" },
  { area: "Search", change: "Global search scoped to this product", owner: "Platform", status: "Live", path: "" },
  { area: "Navigation", change: "Breadcrumbs for module pages", owner: "Platform", status: "Ready", path: "" },
  { area: "Grid", change: "Consistent grid behavior inside this product", owner: "UX", status: "Ready", path: "" },
  { area: "Grid", change: "Column sorting on grids", owner: "UX", status: "Live", path: "" },
  { area: "Grid", change: "Column resizing on grids", owner: "UX", status: "Live", path: "" },
  { area: "Grid", change: "Column reorder on grids", owner: "UX", status: "Live", path: "" },
  { area: "Grid", change: "Column show/hide preferences", owner: "UX", status: "Configured", path: "" },
  { area: "Views", change: "Saved grid views per user", owner: "UX", status: "Ready", path: "" },
  { area: "Export", change: "CSV export for grids", owner: "Data", status: "Live", path: "" },
  { area: "Import", change: "CSV import where relevant", owner: "Data", status: "Live", path: "" },
  { area: "Filters", change: "Advanced filters drawer", owner: "UX", status: "Live", path: "" },
  { area: "Filters", change: "Date range filters", owner: "UX", status: "Ready", path: "" },
  { area: "Filters", change: "Owner/user filters", owner: "UX", status: "Live", path: "" },
  { area: "Filters", change: "Status filters", owner: "UX", status: "Live", path: "" },
  { area: "Create", change: "Quick create button on list pages", owner: "Workflow", status: "Live", path: "" },
  { area: "Details", change: "Detail side panel for selected records", owner: "Workflow", status: "Live", path: "" },
  { area: "Timeline", change: "Activity/timeline panel for records", owner: "Workflow", status: "Ready", path: "" },
  { area: "Bulk", change: "Bulk select and bulk actions", owner: "Workflow", status: "Configured", path: "" },
  { area: "Empty", change: "Empty states per module", owner: "Design", status: "Ready", path: "" },
  { area: "Loading", change: "Loading skeletons for tables/cards", owner: "Design", status: "Ready", path: "" },
  { area: "Responsive", change: "Mobile/tablet responsive layouts", owner: "Design", status: "Ready", path: "" },
];

const productChanges: Record<ProductKey, WorkflowItem[]> = {
  crm: [
    { area: "Dashboard", change: "CRM dashboard opens directly after CRM login", owner: "Sales Ops", status: "Live", path: "/crm" },
    { area: "Leads", change: "Expanded Lead fields", owner: "Sales Ops", status: "Live", path: "/crm/leads" },
    { area: "Contacts", change: "Expanded Contact fields", owner: "Sales Ops", status: "Live", path: "/crm/contacts" },
    { area: "Contacts", change: "Import contacts from any CRM module", owner: "Data", status: "Live", path: "/crm/contacts" },
    { area: "Contacts", change: "Export contacts from any CRM module", owner: "Data", status: "Live", path: "/crm/contacts" },
    { area: "Leads", change: "Lead qualification workflow", owner: "Sales", status: "Ready", path: "/crm/leads" },
    { area: "Leads", change: "Lead scoring field and sorting", owner: "Sales", status: "Live", path: "/crm/leads" },
    { area: "Campaigns", change: "Lead source/campaign tracking", owner: "Marketing", status: "Live", path: "/crm/campaigns" },
    { area: "Conversion", change: "Convert Lead to Contact/Company/Deal", owner: "Sales", status: "Configured", path: "/crm/leads" },
    { area: "Pipeline", change: "Deal pipeline kanban drag and drop", owner: "Sales", status: "Live", path: "/crm/pipeline" },
    { area: "Deals", change: "Deal probability and weighted revenue", owner: "Sales", status: "Live", path: "/crm/deals" },
    { area: "Calendar", change: "Follow-up calendar for leads/deals", owner: "Sales", status: "Live", path: "/crm/calendar" },
    { area: "Calendar", change: "CRM calendar filters fixed", owner: "Sales Ops", status: "Live", path: "/crm/calendar" },
    { area: "Activities", change: "Sales activity logging: call, email, meeting", owner: "Sales", status: "Ready", path: "/crm/activities" },
    { area: "Contacts", change: "Contact lifecycle stages", owner: "Sales", status: "Live", path: "/crm/contacts" },
    { area: "Companies", change: "Account/company ownership tracking", owner: "Sales", status: "Live", path: "/crm/companies" },
    { area: "Quotations", change: "Quotation status workflow", owner: "Revenue", status: "Live", path: "/crm/quotations" },
    { area: "Automation", change: "Quote expiry reminders", owner: "Revenue", status: "Ready", path: "/crm/automation" },
    { area: "Support", change: "Support ticket linkage to contacts/accounts", owner: "Support", status: "Ready", path: "/crm/tickets" },
    { area: "Campaigns", change: "Campaign performance table", owner: "Marketing", status: "Live", path: "/crm/campaigns" },
    { area: "Products", change: "Product/service catalog for quotations", owner: "Revenue", status: "Live", path: "/crm/products" },
    { area: "Automation", change: "CRM automation rules page", owner: "Sales Ops", status: "Live", path: "/crm/automation" },
    { area: "Reports", change: "Sales reports dashboard", owner: "Sales Ops", status: "Live", path: "/crm/reports" },
    { area: "Admin", change: "CRM admin roles and permissions", owner: "Admin", status: "Ready", path: "/crm/admin" },
    { area: "Shell", change: "CRM-only branding, menus, and search", owner: "Platform", status: "Live", path: "/crm" },
  ],
  hrms: [
    { area: "Dashboard", change: "HRMS dashboard opens from /hrms", owner: "HR Ops", status: "Live", path: "/hrms" },
    { area: "Employees", change: "Employee master profile expansion", owner: "HR Ops", status: "Ready", path: "/hrms/employees" },
    { area: "Directory", change: "Employee directory grid improvements", owner: "HR Ops", status: "Ready", path: "/hrms/employee-directory" },
    { area: "Attendance", change: "Attendance dashboard", owner: "HR Ops", status: "Live", path: "/hrms/attendance" },
    { area: "Leave", change: "Leave application workflow", owner: "HR Ops", status: "Live", path: "/hrms/leave" },
    { area: "Leave", change: "Leave approval workflow", owner: "Managers", status: "Live", path: "/hrms/leave" },
    { area: "Payroll", change: "Payroll processing dashboard", owner: "Payroll", status: "Live", path: "/hrms/payroll" },
    { area: "Payroll", change: "Payslip download option", owner: "Payroll", status: "Ready", path: "/hrms/payroll" },
    { area: "Recruitment", change: "Recruitment pipeline", owner: "Talent", status: "Live", path: "/hrms/recruitment" },
    { area: "Recruitment", change: "Candidate profile detail view", owner: "Talent", status: "Ready", path: "/hrms/recruitment" },
    { area: "Onboarding", change: "Onboarding checklist workflow", owner: "HR Ops", status: "Live", path: "/hrms/onboarding" },
    { area: "Documents", change: "Employee document management", owner: "HR Ops", status: "Live", path: "/hrms/documents" },
    { area: "Performance", change: "Performance review workflow", owner: "Managers", status: "Live", path: "/hrms/performance" },
    { area: "Performance", change: "Goals/KRA tracking", owner: "Managers", status: "Ready", path: "/hrms/performance" },
    { area: "Dashboard", change: "Manager dashboard", owner: "Managers", status: "Live", path: "/hrms/manager-dashboard" },
    { area: "ESS", change: "Employee self-service portal", owner: "Employees", status: "Live", path: "/hrms/ess" },
    { area: "Timesheets", change: "Timesheet submission workflow", owner: "Employees", status: "Ready", path: "/hrms/timesheets" },
    { area: "Timesheets", change: "Timesheet approval workflow", owner: "Managers", status: "Ready", path: "/hrms/timesheets" },
    { area: "Assets", change: "Asset assignment tracking", owner: "Admin", status: "Live", path: "/hrms/assets" },
    { area: "Exit", change: "Exit management workflow", owner: "HR Ops", status: "Live", path: "/hrms/exit" },
    { area: "Helpdesk", change: "Helpdesk tickets for employees", owner: "HR Ops", status: "Live", path: "/hrms/helpdesk" },
    { area: "Compliance", change: "Statutory compliance module", owner: "Compliance", status: "Live", path: "/hrms/statutory-compliance" },
    { area: "Compliance", change: "Background verification workflow", owner: "Compliance", status: "Live", path: "/hrms/background-verification" },
    { area: "Reports", change: "HR reports and analytics", owner: "HR Ops", status: "Live", path: "/hrms/reports" },
    { area: "Shell", change: "HRMS-only branding, menus, and search", owner: "Platform", status: "Live", path: "/hrms" },
  ],
  pms: [
    { area: "Dashboard", change: "PMS dashboard opens from /pms", owner: "PMO", status: "Live", path: "/pms" },
    { area: "Projects", change: "Project list with health/status indicators", owner: "PMO", status: "Live", path: "/pms/projects" },
    { area: "Projects", change: "Project detail dashboard", owner: "PMO", status: "Live", path: "/pms/projects" },
    { area: "Projects", change: "Create project workflow", owner: "PMO", status: "Live", path: "/pms/projects/new" },
    { area: "Tasks", change: "Task board/kanban workflow", owner: "Delivery", status: "Live", path: "/pms/projects" },
    { area: "Sprints", change: "Sprint planning", owner: "Delivery", status: "Live", path: "/pms/sprints" },
    { area: "Backlog", change: "Backlog management", owner: "Product", status: "Live", path: "/pms/backlog" },
    { area: "Issues", change: "Issue navigator", owner: "Delivery", status: "Live", path: "/pms/navigator" },
    { area: "Gantt", change: "Gantt chart view", owner: "PMO", status: "Live", path: "/pms/gantt" },
    { area: "Timeline", change: "Timeline dependency view", owner: "PMO", status: "Live", path: "/pms/dependencies" },
    { area: "Milestones", change: "Milestone tracking", owner: "PMO", status: "Ready", path: "/pms/milestones" },
    { area: "Roadmap", change: "Roadmap planning", owner: "Product", status: "Live", path: "/pms/roadmap" },
    { area: "Calendar", change: "Project calendar", owner: "PMO", status: "Live", path: "/pms/calendar" },
    { area: "Time", change: "Time tracking per task", owner: "Delivery", status: "Live", path: "/pms/time-tracking" },
    { area: "Resources", change: "Resource utilization view", owner: "PMO", status: "Live", path: "/pms/resource-utilization" },
    { area: "Teams", change: "Team workload dashboard", owner: "PMO", status: "Live", path: "/pms/teams-live" },
    { area: "Files", change: "Files per project/task", owner: "Delivery", status: "Live", path: "/pms/files" },
    { area: "Client", change: "Client portal", owner: "PMO", status: "Live", path: "/pms/client-portal" },
    { area: "Reports", change: "Project reports", owner: "PMO", status: "Live", path: "/pms/reports" },
    { area: "Workflow", change: "Workflow configuration", owner: "Admin", status: "Live", path: "/pms/workflows" },
    { area: "Templates", change: "Project templates", owner: "PMO", status: "Ready", path: "/pms/templates" },
    { area: "Releases", change: "Release planning", owner: "Delivery", status: "Live", path: "/pms/releases" },
    { area: "AI", change: "Automation/AI planner page", owner: "PMO", status: "Live", path: "/pms/automation" },
    { area: "Admin", change: "PMS admin and security settings", owner: "Admin", status: "Live", path: "/pms/admin" },
    { area: "Shell", change: "PMS-only branding, menus, and search", owner: "Platform", status: "Live", path: "/pms" },
  ],
};

const labels: Record<ProductKey, { title: string; subtitle: string; tone: string }> = {
  crm: { title: "CRM Workflow Center", subtitle: "Sales, marketing, support, quotations, automation, and account operations.", tone: "text-emerald-700 bg-emerald-50 border-emerald-200" },
  hrms: { title: "HRMS Workflow Center", subtitle: "People operations, payroll, attendance, compliance, ESS, and approvals.", tone: "text-blue-700 bg-blue-50 border-blue-200" },
  pms: { title: "PMS Workflow Center", subtitle: "Projects, delivery planning, issues, resources, releases, clients, and reports.", tone: "text-violet-700 bg-violet-50 border-violet-200" },
};

export function ProductWorkflowCenter({ product }: { product: ProductKey }) {
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const items = productChanges[product];
  const productHome = items[0]?.path || "/";
  const productCommonChanges = useMemo(() => commonChanges.map((item) => ({ ...item, path: productHome })), [productHome]);
  const visibleItems = useMemo(() => {
    const text = query.toLowerCase();
    return items.filter((item) => {
      const matchesText = Object.values(item).join(" ").toLowerCase().includes(text);
      const matchesStatus = status === "all" || item.status === status;
      return matchesText && matchesStatus;
    });
  }, [items, query, status]);
  const exportPayload = [...productCommonChanges.map((item) => ({ scope: "Product Platform", ...item })), ...items.map((item) => ({ scope: labels[product].title, ...item }))];
  const liveCount = items.filter((item) => item.status === "Live").length;
  const summaryTiles: SummaryTile[] = [
    ["Platform", productCommonChanges.length, Layers3],
    ["Product", items.length, ListChecks],
    ["Live", liveCount, ShieldCheck],
    ["Grid Ops", 8, Columns3],
    ["Workflow Ops", 9, Settings2],
  ];

  return (
    <section className="space-y-4">
      <Card className={`border ${labels[product].tone}`}>
        <CardContent className="grid gap-4 p-5 lg:grid-cols-[1fr_auto] lg:items-center">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Workflow className="h-4 w-4" />
              {labels[product].title}
            </div>
            <h2 className="mt-2 text-xl font-semibold tracking-tight">{liveCount}/25 product workflows live</h2>
            <p className="mt-1 text-sm opacity-80">{labels[product].subtitle}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => exportRows(`${product}-workflow-changes.csv`, exportPayload)}>
              <Download className="h-4 w-4" />
              Export Changes
            </Button>
            <Button variant="outline" onClick={() => exportRows(`${product}-import-template.csv`, items.map((item) => ({ area: item.area, change: item.change, owner: "", status: "", path: "" })))}>
              <Import className="h-4 w-4" />
              Import Template
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-5">
        {summaryTiles.map(([label, value, Icon]) => (
          <Card key={String(label)}>
            <CardContent className="flex items-center gap-3 p-4">
              <div className="rounded-lg bg-primary/10 p-2 text-primary">
                <Icon className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xl font-semibold">{value}</p>
                <p className="text-xs text-muted-foreground">{label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle className="text-base">Product Operating Layer</CardTitle>
          <div className="flex flex-wrap gap-2">
            {["Saved views", "Bulk actions", "Columns", "Date range", "Owner", "Status"].map((item) => (
              <Badge key={item} variant="outline">{item}</Badge>
            ))}
          </div>
        </CardHeader>
        <CardContent className="grid gap-2 md:grid-cols-2 xl:grid-cols-5">
          {productCommonChanges.map((item, index) => (
            <div key={item.change} className="rounded-md border bg-muted/20 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-muted-foreground">{String(index + 1).padStart(2, "0")} {item.area}</span>
                <Badge className={statusClass(item.status)}>{item.status}</Badge>
              </div>
              <p className="mt-2 text-sm font-medium leading-snug">{item.change}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle className="text-base">Product Workflows</CardTitle>
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="flex min-w-0 items-center gap-2 rounded-md border px-3 py-2">
              <Search className="h-4 w-4 text-muted-foreground" />
              <Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search workflows..." className="h-6 border-0 p-0 shadow-none focus-visible:ring-0" />
            </div>
            <NativeSelect className="h-10 rounded-md border bg-background px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="all">All statuses</option>
              <option value="Live">Live</option>
              <option value="Ready">Ready</option>
              <option value="Configured">Configured</option>
            </NativeSelect>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <GridTable gridId="components/product/ProductWorkflowCenter:table-1" className="w-full min-w-[900px] text-sm">
              <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3"><GripVertical className="h-4 w-4" /></th>
                  <th className="px-4 py-3">Area</th>
                  <th className="px-4 py-3">Workflow Change</th>
                  <th className="px-4 py-3">Owner</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleItems.map((item, index) => (
                  <tr {...recordPreviewProps(item)} key={item.change} className="border-t hover:bg-muted/30">
                    <td className="px-4 py-3 text-muted-foreground">{index + 1}</td>
                    <td className="px-4 py-3 font-medium">{item.area}</td>
                    <td className="px-4 py-3">{item.change}</td>
                    <td className="px-4 py-3">{item.owner}</td>
                    <td className="px-4 py-3"><Badge className={statusClass(item.status)}>{item.status}</Badge></td>
                    <td className="px-4 py-3">
                      <a className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium hover:bg-muted" href={item.path}>
                        Open
                        <ArrowRight className="h-3 w-3" />
                      </a>
                    </td>
                  </tr>
                ))}
                {!visibleItems.length ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-muted-foreground">
                      <Filter className="mx-auto mb-2 h-5 w-5" />
                      No workflows match the current filters.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </GridTable>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-3">
        {["Review saved view", "Run bulk workflow", "Refresh module data"].map((label, index) => (
          <Button key={label} variant="outline" className="justify-start">
            {index === 0 ? <Columns3 className="h-4 w-4" /> : index === 1 ? <ListChecks className="h-4 w-4" /> : <RefreshCw className="h-4 w-4" />}
            {label}
          </Button>
        ))}
      </div>
    </section>
  );
}

function statusClass(status: WorkflowItem["status"]) {
  if (status === "Live") return "bg-emerald-100 text-emerald-700 hover:bg-emerald-100";
  if (status === "Configured") return "bg-amber-100 text-amber-700 hover:bg-amber-100";
  return "bg-blue-100 text-blue-700 hover:bg-blue-100";
}
