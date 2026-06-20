import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { CheckCircle2, Link2, Network, RefreshCw, ShieldCheck } from "lucide-react";
import { api } from "@/services/api";
import { setBusinessOsEnabledModules } from "@/appRegistry";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type BOSModule = {
  module_key: string;
  display_name: string;
  enabled: boolean;
  is_financial_backbone?: boolean;
  home_path?: string;
};

type IntegrationRule = {
  id: number;
  rule_key: string;
  source_module: string;
  target_module: string;
  event_name: string;
  action_name: string;
  enabled: boolean;
  source_enabled: boolean;
  target_enabled: boolean;
  effective: boolean;
};

type LifecycleEvent = {
  id: number;
  event_name: string;
  module_key: string;
  status: string;
  message?: string;
  created_at?: string;
};

const tabs = [
  { label: "Modules", to: "/admin/business-os/modules" },
  { label: "Integrations", to: "/admin/business-os/integrations" },
  { label: "Lifecycle", to: "/admin/business-os/lifecycle" },
];

export default function BusinessOSAdminPage() {
  const location = useLocation();
  const view = location.pathname.includes("/integrations") ? "integrations" : location.pathname.includes("/lifecycle") ? "lifecycle" : "modules";
  const [modules, setModules] = useState<BOSModule[]>([]);
  const [enabled, setEnabled] = useState<string[]>([]);
  const [combinations, setCombinations] = useState<Array<{ name: string; modules: string[] }>>([]);
  const [rules, setRules] = useState<IntegrationRule[]>([]);
  const [events, setEvents] = useState<LifecycleEvent[]>([]);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const enabledSet = useMemo(() => new Set(enabled), [enabled]);

  const load = async () => {
    const moduleResponse = await api.get("/business-os/modules");
    setModules(moduleResponse.data.modules || []);
    setEnabled(moduleResponse.data.enabled_modules || []);
    setCombinations(moduleResponse.data.supported_combinations || []);
    setBusinessOsEnabledModules(moduleResponse.data.enabled_modules || []);
    const rulesResponse = await api.get("/business-os/integration-rules");
    setRules(rulesResponse.data || []);
    const lifecycleResponse = await api.get("/business-os/lifecycle/fam/module/fam").catch(() => ({ data: [] }));
    setEvents(lifecycleResponse.data || []);
  };

  useEffect(() => {
    load().catch((error) => setMessage(error?.response?.data?.detail || "Could not load Business OS settings."));
  }, [location.pathname]);

  const toggle = (moduleKey: string) => {
    setEnabled((items) => items.includes(moduleKey) ? items.filter((item) => item !== moduleKey) : [...items, moduleKey]);
  };

  const applyCombination = (moduleKeys: string[]) => setEnabled(moduleKeys);

  const save = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const response = await api.put("/business-os/modules", { enabled_modules: enabled });
      setModules(response.data.modules || []);
      setEnabled(response.data.enabled_modules || []);
      setBusinessOsEnabledModules(response.data.enabled_modules || []);
      setMessage("Business OS module configuration saved. Disabled modules keep historical data but hide routes and block APIs.");
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || "Could not save module configuration.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Network className="h-5 w-5 text-primary" />
            <h1 className="text-2xl font-semibold tracking-tight">Business OS Modular Foundation</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">Enable only the modules each tenant needs. FAM can act as the financial backbone, while CRM, Sales & Inventory with POS, PMS, HRMS, AI, Portals, and Communication remain optional.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => load()}><RefreshCw className="h-4 w-4" />Refresh</Button>
          {view === "modules" ? <Button onClick={save} disabled={saving}>{saving ? "Saving..." : "Save modules"}</Button> : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {tabs.map((tab) => <Button key={tab.to} asChild variant={location.pathname === tab.to ? "default" : "outline"}><Link to={tab.to}>{tab.label}</Link></Button>)}
      </div>

      {message ? <div className="rounded-md border bg-muted px-4 py-3 text-sm">{message}</div> : null}

      {view === "modules" ? (
        <div className="grid gap-4 xl:grid-cols-[1fr_22rem]">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {modules.map((module) => (
              <Card key={module.module_key}>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between gap-2 text-base">
                    {module.display_name}
                    <Badge variant={enabledSet.has(module.module_key) ? "default" : "outline"}>{enabledSet.has(module.module_key) ? "Enabled" : "Disabled"}</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 text-sm">
                  <p className="text-muted-foreground">{module.is_financial_backbone ? "Financial backbone for postings and statutory books." : "Optional Business OS module."}</p>
                  <Button variant={enabledSet.has(module.module_key) ? "outline" : "default"} className="w-full" onClick={() => toggle(module.module_key)}>
                    {enabledSet.has(module.module_key) ? "Disable" : "Enable"}
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardHeader><CardTitle className="text-base">Supported Combinations</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {combinations.map((combo) => (
                <button key={combo.name} type="button" className="w-full rounded-md border p-3 text-left text-sm hover:bg-muted" onClick={() => applyCombination(combo.modules)}>
                  <span className="font-medium">{combo.name}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">{combo.modules.join(", ")}</span>
                </button>
              ))}
            </CardContent>
          </Card>
        </div>
      ) : null}

      {view === "integrations" ? (
        <div className="grid gap-3">
          {rules.map((rule) => (
            <Card key={rule.id}>
              <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="font-medium">{rule.rule_key}</p>
                  <p className="text-sm text-muted-foreground">
                    {rule.source_module} / {rule.event_name} {"->"} {rule.target_module} / {rule.action_name}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge variant={rule.source_enabled ? "default" : "outline"}>{rule.source_module}</Badge>
                  <Badge variant={rule.target_enabled ? "default" : "outline"}>{rule.target_module}</Badge>
                  <Badge variant={rule.effective ? "default" : "secondary"}>{rule.effective ? "Effective" : "Skipped"}</Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : null}

      {view === "lifecycle" ? (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ShieldCheck className="h-4 w-4" />Lifecycle Evidence</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {events.length ? events.map((event) => (
              <div key={event.id} className="flex gap-3 rounded-md border p-3 text-sm">
                <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />
                <div>
                  <p className="font-medium">{event.event_name} / {event.module_key}</p>
                  <p className="text-muted-foreground">{event.message || event.status}</p>
                </div>
              </div>
            )) : <p className="text-sm text-muted-foreground">No lifecycle events selected. Module enable/disable actions will appear here.</p>}
            <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground"><Link2 className="mr-2 inline h-4 w-4" />Entity lifecycle APIs are available for CRM, SRM inventory, PMS, and FAM links without showing fake records.</div>
          </CardContent>
        </Card>
      ) : null}
    </section>
  );
}
