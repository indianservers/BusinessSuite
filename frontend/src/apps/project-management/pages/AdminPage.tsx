import { Link } from "react-router-dom";
import {
  BarChart3,
  Bell,
  BookOpen,
  ClipboardList,
  FileCheck2,
  GitBranch,
  Network,
  Settings,
  ShieldCheck,
  Users,
  Workflow,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const adminSections = [
  {
    title: "Workspace Settings",
    description: "Organization preferences, repository mappings, import/export settings, and notification defaults.",
    href: "/pms/settings",
    icon: Settings,
    status: "Operational",
  },
  {
    title: "Users & Permissions",
    description: "Open the PMS security workspace for role visibility, access review, and permission checks.",
    href: "/pms/security",
    icon: ShieldCheck,
    status: "Configured",
  },
  {
    title: "Projects",
    description: "Review project records, create new workspaces, and manage active delivery portfolios.",
    href: "/pms/projects",
    icon: ClipboardList,
    status: "Live",
  },
  {
    title: "Project Templates",
    description: "Manage reusable delivery patterns through the templates workspace.",
    href: "/pms/templates",
    icon: BookOpen,
    status: "Available",
  },
  {
    title: "Task Workflows",
    description: "Review workflow states, boards, dependencies, and delivery execution controls.",
    href: "/pms/workflows",
    icon: GitBranch,
    status: "Available",
  },
  {
    title: "Automation Rules",
    description: "Configure AI-assisted planning, automation suggestions, and workflow accelerators.",
    href: "/pms/automation",
    icon: Workflow,
    status: "Available",
  },
  {
    title: "Audit & Reports",
    description: "Open operational reports for delivery, risks, utilization, timesheets, and portfolio status.",
    href: "/pms/reports",
    icon: BarChart3,
    status: "Live",
  },
  {
    title: "Apps & Integrations",
    description: "Connect repositories and integration workspaces for source control, deployments, and webhooks.",
    href: "/pms/apps",
    icon: Network,
    status: "Ready",
  },
  {
    title: "Plans",
    description: "Manage planning and subscription-style controls through the plans workspace.",
    href: "/pms/plans",
    icon: FileCheck2,
    status: "Available",
  },
  {
    title: "Notifications",
    description: "Review collaboration, workload, calendar, and timeline areas that drive project notifications.",
    href: "/pms/calendar",
    icon: Bell,
    status: "Linked",
  },
  {
    title: "Resource Governance",
    description: "Monitor capacity, workload, and resource utilization across teams.",
    href: "/pms/resource-utilization",
    icon: Users,
    status: "Available",
  },
];

export default function AdminPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="page-title">Admin</h1>
          <p className="page-description">Administrative controls for PMS configuration, governance, integrations, and delivery operations.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline"><Link to="/pms/settings">Settings</Link></Button>
          <Button asChild><Link to="/pms/projects/new">Create Project</Link></Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {adminSections.map((item) => {
          const Icon = item.icon;
          return (
            <Card key={item.title}>
              <CardHeader className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Icon className="h-4 w-4 text-primary" />
                    {item.title}
                  </CardTitle>
                  <Badge variant="outline">{item.status}</Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="min-h-12 text-sm text-muted-foreground">{item.description}</p>
                <Button asChild size="sm" variant="outline">
                  <Link to={item.href}>Open</Link>
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
