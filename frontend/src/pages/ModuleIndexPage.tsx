import { Link } from "react-router-dom";
import { Briefcase, Building2, FolderKanban, LogIn, Receipt, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAuthStore } from "@/store/authStore";

const modules = [
  {
    key: "hrms",
    name: "AI HRMS",
    label: "Human Resource Management",
    description: "Employees, payroll, attendance, leave, recruitment, and self-service.",
    icon: Building2,
    homePath: "/hrms",
    loginPath: "/hrms/login",
    tone: "bg-blue-600",
  },
  {
    key: "crm",
    name: "VyaparaCRM",
    label: "Customer Relationship Management",
    description: "Leads, customers, deals, activities, campaigns, quotes, and sales follow-ups.",
    icon: Briefcase,
    homePath: "/crm",
    loginPath: "/crm/login",
    tone: "bg-emerald-600",
  },
  {
    key: "pms",
    name: "KaryaFlow PMS",
    label: "Project Management Software",
    description: "Projects, tasks, sprints, milestones, reports, workload, risks, and delivery plans.",
    icon: FolderKanban,
    homePath: "/pms",
    loginPath: "/pms/login",
    tone: "bg-violet-600",
  },
  {
    key: "srm",
    name: "Sales & Revenue Management",
    label: "SRM",
    description: "Manage sales orders, contracts, billing, invoices, collections, and revenue profitability.",
    icon: Receipt,
    homePath: "/srm",
    loginPath: "/srm/login",
    tone: "bg-amber-600",
  },
];

export default function ModuleIndexPage() {
  const { isAuthenticated, isHydrated } = useAuthStore();

  return (
    <main className="min-h-screen bg-background">
      <section className="border-b bg-card">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-10 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5" />
              Business Suite
            </div>
            <h1 className="text-3xl font-semibold tracking-tight">Choose a module</h1>
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
              Open CRM, HRMS, PMS, or SRM from one index page. Sign in to the module you want to use.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/login"><LogIn className="h-4 w-4" /> General login</Link>
          </Button>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-5 py-8 md:grid-cols-4">
        {modules.map((module) => {
          const Icon = module.icon;
          return (
            <Card key={module.key} className="overflow-hidden transition duration-200 hover:-translate-y-1 hover:shadow-lg">
              <CardContent className="flex h-full flex-col p-0">
                <div className={`${module.tone} p-5 text-white`}>
                  <Icon className="h-8 w-8" />
                  <h2 className="mt-4 text-xl font-semibold">{module.name}</h2>
                  <p className="text-sm text-white/80">{module.label}</p>
                </div>
                <div className="flex flex-1 flex-col p-5">
                  <p className="text-sm text-muted-foreground">{module.description}</p>
                  <div className="mt-6 grid gap-2">
                    <Button asChild>
                      <Link to={isHydrated && isAuthenticated ? module.homePath : module.loginPath}>
                        {!isHydrated ? "Loading..." : module.key === "srm" ? "Open SRM" : isAuthenticated ? `Open ${module.label}` : "Sign in"}
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </section>
    </main>
  );
}
