import { Link } from "react-router-dom";
import { Briefcase, Building2, FolderKanban, Landmark, LogIn, Package, Receipt, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { moduleDefaultCredentials } from "@/lib/defaultCredentials";
import { useAuthStore } from "@/store/authStore";

const modules = [
  {
    key: "hrms",
    credentialKey: "hrms",
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
    credentialKey: "crm",
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
    credentialKey: "project_management",
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
    credentialKey: "srm",
    name: "Sales & Revenue Management",
    label: "SRM",
    description: "Manage sales orders, contracts, billing, invoices, collections, and revenue profitability.",
    icon: Receipt,
    homePath: "/srm",
    loginPath: "/srm/login",
    tone: "bg-amber-600",
  },
  {
    key: "fam",
    credentialKey: "fam",
    name: "Finance & Accounting Management",
    label: "FAM",
    description: "Manage financial settings, chart of accounts, ledgers, opening balances, branches, cost centers, and audit-ready books.",
    icon: Landmark,
    homePath: "/fam",
    loginPath: "/fam/login",
    tone: "bg-cyan-700",
  },
  {
    key: "inventory",
    credentialKey: null,
    name: "Vyapara ERP Inventory",
    label: "Inventory",
    description: "Products, stock, warehouses, purchases, sales, POS, reports, and GST-ready inventory operations from the cloned Vyapara ERP app.",
    icon: Package,
    homePath: "/inventory",
    loginPath: "/login",
    tone: "bg-teal-700",
  },
] as const;

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
              Open CRM, HRMS, PMS, SRM, FAM, or Inventory from one index page. Sign in to the module you want to use.
            </p>
          </div>
          <Button asChild variant="outline">
            <Link to="/login"><LogIn className="h-4 w-4" /> General login</Link>
          </Button>
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-5 py-8 md:grid-cols-2 lg:grid-cols-3">
        {modules.map((module) => {
          const Icon = module.icon;
          const defaultLogin = module.credentialKey ? moduleDefaultCredentials[module.credentialKey][0] : null;
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
                  {defaultLogin ? (
                    <dl className="mt-4 grid gap-1 rounded-md border bg-muted/40 p-3 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <dt className="font-medium text-muted-foreground">Default email</dt>
                        <dd className="text-right font-semibold text-foreground">{defaultLogin.email}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <dt className="font-medium text-muted-foreground">Default password</dt>
                        <dd className="text-right font-semibold text-foreground">{defaultLogin.password}</dd>
                      </div>
                    </dl>
                  ) : null}
                  <div className="mt-6 grid gap-2">
                    <Button asChild>
                      <Link to={module.key === "inventory" ? module.homePath : isHydrated && isAuthenticated ? module.homePath : module.loginPath}>
                        {!isHydrated ? "Loading..." : isAuthenticated || module.key === "srm" || module.key === "inventory" ? `Open ${module.label}` : "Sign in"}
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
