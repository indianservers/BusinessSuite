import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Bot, Gauge, Layers3, RefreshCw, Search, ShieldCheck } from "lucide-react";
import { api } from "@/services/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Widget = { title: string; status: string; evidence: string };
type Report = { key: string; title: string; enabled: boolean; required_modules: string[]; reason: string };
type RoleRow = { role: string; available: boolean; permissions: string[]; reason: string };
type Section = { module: string; title: string; description: string };
type AiAnswer = { allowed: boolean; answer: string; module: string; evidence: { enabled_modules: string[] } };

const tabs = [
  { label: "Dashboard", to: "/business-os/dashboard" },
  { label: "Customer 720", to: "/business-os/customer-720" },
  { label: "Reports", to: "/business-os/reports" },
  { label: "AI", to: "/business-os/ai" },
];

function viewFrom(pathname: string) {
  if (pathname.includes("/customer-720")) return "customer";
  if (pathname.includes("/reports")) return "reports";
  if (pathname.includes("/ai")) return "ai";
  return "dashboard";
}

export default function BusinessOSWorkspacePage() {
  const location = useLocation();
  const view = viewFrom(location.pathname);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [widgets, setWidgets] = useState<Widget[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [roles, setRoles] = useState<RoleRow[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [question, setQuestion] = useState("Show CRM pipeline");
  const [answer, setAnswer] = useState<AiAnswer | null>(null);
  const [message, setMessage] = useState("");

  const enabledLabel = useMemo(() => enabled.join(", ") || "No modules enabled", [enabled]);

  const load = async () => {
    setMessage("");
    const [dashboard, reportCatalog, rbac, customer] = await Promise.all([
      api.get("/business-os/dashboard"),
      api.get("/business-os/reports/catalog"),
      api.get("/business-os/rbac/catalog"),
      api.get("/business-os/customer-720"),
    ]);
    setEnabled(dashboard.data.enabled_modules || []);
    setWidgets(dashboard.data.widgets || []);
    setReports(reportCatalog.data.reports || []);
    setRoles(rbac.data.roles || []);
    setSections(customer.data.sections || []);
  };

  useEffect(() => {
    load().catch((error) => setMessage(error?.response?.data?.detail || "Could not load Business OS workspace."));
  }, [location.pathname]);

  const ask = async () => {
    const response = await api.post("/business-os/ai/ask", { question });
    setAnswer(response.data);
  };

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Layers3 className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">Business OS</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Dynamic operating layer. Screens, reports, roles, Customer 720 and AI only use enabled modules.</p>
        </div>
        <Button variant="outline" onClick={load}><RefreshCw className="h-4 w-4" />Refresh</Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => <Button key={tab.to} asChild variant={(location.pathname === tab.to || (location.pathname === "/business-os" && tab.to.endsWith("/dashboard"))) ? "default" : "outline"}><Link to={tab.to}>{tab.label}</Link></Button>)}
      </div>

      <Card>
        <CardContent className="flex flex-col gap-2 p-4 text-sm md:flex-row md:items-center md:justify-between">
          <span className="font-medium">Enabled modules</span>
          <span className="text-muted-foreground">{enabledLabel}</span>
        </CardContent>
      </Card>

      {message ? <div className="rounded-md border bg-muted px-4 py-3 text-sm">{message}</div> : null}

      {view === "dashboard" ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {widgets.map((widget) => (
            <Card key={widget.title}>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base"><Gauge className="h-4 w-4 text-primary" />{widget.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <Badge>{widget.status}</Badge>
                <p className="text-muted-foreground">{widget.evidence}</p>
              </CardContent>
            </Card>
          ))}
          {!widgets.length ? <p className="rounded-md border p-4 text-sm text-muted-foreground">No dashboard widgets are available because no matching modules are enabled.</p> : null}
        </div>
      ) : null}

      {view === "reports" ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {reports.map((report) => (
            <Card key={report.key} className={report.enabled ? "" : "opacity-70"}>
              <CardHeader className="pb-2"><CardTitle className="text-base">{report.title}</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                <Badge variant={report.enabled ? "default" : "secondary"}>{report.enabled ? "Enabled" : "Disabled"}</Badge>
                <p className="text-muted-foreground">{report.reason}</p>
                <p className="text-xs text-muted-foreground">Requires: {report.required_modules.join(", ") || "Business OS"}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {view === "customer" ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sections.map((section) => (
            <Card key={section.module}>
              <CardHeader className="pb-2"><CardTitle className="text-base">{section.title}</CardTitle></CardHeader>
              <CardContent className="text-sm text-muted-foreground">{section.description}</CardContent>
            </Card>
          ))}
          {!sections.length ? <p className="rounded-md border p-4 text-sm text-muted-foreground">Customer 720 has no enabled-module sections. No fake placeholders are shown.</p> : null}
        </div>
      ) : null}

      {view === "ai" ? (
        <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Bot className="h-4 w-4 text-primary" />Module-Aware AI Copilot</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="flex gap-2">
                <Input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask about enabled modules" />
                <Button onClick={ask}><Search className="h-4 w-4" />Ask</Button>
              </div>
              {answer ? (
                <div className="rounded-md border p-4 text-sm">
                  <Badge variant={answer.allowed ? "default" : "destructive"}>{answer.allowed ? "Allowed" : "Blocked"}</Badge>
                  <p className="mt-2">{answer.answer}</p>
                  <p className="mt-2 text-xs text-muted-foreground">Evidence: {answer.evidence.enabled_modules.join(", ")}</p>
                </div>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4 text-primary" />Module-Aware Roles</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {roles.map((role) => (
                <div key={role.role} className="rounded-md border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{role.role}</span>
                    <Badge variant={role.available ? "default" : "secondary"}>{role.available ? "Available" : "Hidden"}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{role.reason}</p>
                  {role.available ? <p className="mt-1 text-xs text-muted-foreground">{role.permissions.join(", ") || "No disabled-module permissions exposed"}</p> : null}
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </section>
  );
}
