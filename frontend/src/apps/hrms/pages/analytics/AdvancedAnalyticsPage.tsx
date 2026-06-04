import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BarChart3, Factory, Gauge, ShieldAlert, TrendingDown, TrendingUp, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { enterpriseApi, reportsApi } from "@/services/api";
import { usePageTitle } from "@/hooks/use-page-title";
import { toast } from "@/hooks/use-toast";

const metricCards = [
  { code: "absenteeism", title: "Absenteeism", icon: TrendingDown },
  { code: "pay_equity", title: "Pay Equity", icon: BarChart3 },
  { code: "manager_effectiveness", title: "Manager Effectiveness", icon: Users },
  { code: "span_of_control", title: "Span of Control", icon: Gauge },
  { code: "attrition_trend", title: "Attrition Trend", icon: AlertTriangle },
  { code: "dei_representation", title: "DE&I Representation", icon: TrendingUp },
] as const;

type Drilldown = {
  metric: string;
  summary: Record<string, number | string>;
  rows: Array<Record<string, unknown>>;
};

type DomainPack = {
  id: number;
  pack_key: string;
  pack_name: string;
  status: string;
};

type SafetyIncident = {
  id: number;
  incident_date: string;
  incident_type: string;
  severity: string;
  status: string;
  location?: string;
};

const numberValue = (value: unknown) => Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

export default function AdvancedAnalyticsPage() {
  usePageTitle("Advanced Analytics");
  const qc = useQueryClient();
  const [metric, setMetric] = useState("absenteeism");
  const [filters, setFilters] = useState({
    department_id: "",
    grade_band_id: "",
    location_id: "",
    employment_type: "",
    tenure_band: "",
  });
  const [incident, setIncident] = useState({
    incident_date: new Date().toISOString().slice(0, 10),
    incident_type: "Near Miss",
    severity: "Low",
    location: "",
    description: "",
  });

  const params = useMemo(() => {
    const clean: Record<string, unknown> = { metric };
    Object.entries(filters).forEach(([key, value]) => {
      if (value) clean[key] = ["department_id", "grade_band_id", "location_id"].includes(key) ? Number(value) : value;
    });
    return clean;
  }, [filters, metric]);

  const definitions = useQuery({
    queryKey: ["governed-hr-metrics"],
    queryFn: () => reportsApi.governedMetrics().then((r) => r.data),
  });
  const drilldown = useQuery({
    queryKey: ["analytics-drilldown", params],
    queryFn: () => reportsApi.analyticsDrilldown(params).then((r) => r.data as Drilldown),
  });
  const packs = useQuery({
    queryKey: ["domain-packs"],
    queryFn: () => enterpriseApi.domainPacks().then((r) => r.data as DomainPack[]),
  });
  const manufacturingEnabled = (packs.data || []).some((pack) => pack.pack_key === "manufacturing" && pack.status === "Enabled");
  const safetyIncidents = useQuery({
    queryKey: ["manufacturing-safety-incidents"],
    queryFn: () => enterpriseApi.manufacturingSafetyIncidents().then((r) => r.data as SafetyIncident[]),
    retry: false,
    enabled: manufacturingEnabled,
  });

  const enableManufacturing = useMutation({
    mutationFn: () => enterpriseApi.enableDomainPack({ pack_key: "manufacturing", config_json: { enabled_from: new Date().toISOString() } }),
    onSuccess: () => {
      toast({ title: "Manufacturing pack enabled" });
      qc.invalidateQueries({ queryKey: ["domain-packs"] });
      qc.invalidateQueries({ queryKey: ["manufacturing-safety-incidents"] });
    },
  });

  const createIncident = useMutation({
    mutationFn: () => enterpriseApi.createManufacturingSafetyIncident(incident),
    onSuccess: () => {
      toast({ title: "Safety incident recorded" });
      qc.invalidateQueries({ queryKey: ["manufacturing-safety-incidents"] });
      setIncident({ ...incident, description: "", location: "" });
    },
    onError: () => toast({ title: "Enable manufacturing pack first", variant: "destructive" }),
  });

  const selectedDefinition = (definitions.data || []).find((item: { code: string }) => item.code === metric);
  const summaryEntries = Object.entries(drilldown.data?.summary || {});

  return (
    <div className="space-y-5">
      <div className="rounded-lg border bg-card p-5">
        <p className="text-xs font-semibold uppercase text-muted-foreground">HRMS Intelligence</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Advanced Analytics</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Governed HR metrics with drilldowns by department, band, location, employment type, and tenure.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-6">
        {metricCards.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.code}
              type="button"
              onClick={() => setMetric(item.code)}
              className={`rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted/50 ${metric === item.code ? "border-primary" : ""}`}
            >
              <Icon className="mb-3 h-5 w-5 text-primary" />
              <p className="text-sm font-medium">{item.title}</p>
            </button>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Metric Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-5">
          {[
            ["department_id", "Department ID"],
            ["grade_band_id", "Grade/Band ID"],
            ["location_id", "Location ID"],
            ["employment_type", "Employment Type"],
            ["tenure_band", "Tenure Band"],
          ].map(([key, label]) => (
            <div key={key} className="space-y-1.5">
              <Label>{label}</Label>
              {key === "tenure_band" ? (
                <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={filters.tenure_band} onChange={(e) => setFilters({ ...filters, tenure_band: e.target.value })}>
                  <option value="">All</option>
                  {["0-1", "1-3", "3-5", "5+"].map((value) => <option key={value}>{value}</option>)}
                </select>
              ) : (
                <Input value={(filters as Record<string, string>)[key]} onChange={(e) => setFilters({ ...filters, [key]: e.target.value })} />
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr_24rem]">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{selectedDefinition?.name || metric}</CardTitle>
            <p className="text-sm text-muted-foreground">{selectedDefinition?.formula_json?.description || "Live governed metric drilldown."}</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              {summaryEntries.length ? summaryEntries.map(([key, value]) => (
                <div key={key} className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">{key.replace(/_/g, " ")}</p>
                  <p className="mt-1 text-xl font-semibold">{numberValue(value)}</p>
                </div>
              )) : <p className="rounded-lg border p-4 text-sm text-muted-foreground sm:col-span-3">No data for the selected metric and filters.</p>}
            </div>
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full min-w-[640px] text-sm">
                <tbody>
                  {(drilldown.data?.rows || []).slice(0, 12).map((row, index) => (
                    <tr key={index} className="border-b last:border-0">
                      {Object.entries(row).map(([key, value]) => (
                        <td key={key} className="px-3 py-2">
                          <span className="text-xs text-muted-foreground">{key.replace(/_/g, " ")} </span>
                          <span className="font-medium">{String(value ?? "-")}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!drilldown.isLoading && !drilldown.data?.rows?.length && <p className="p-4 text-sm text-muted-foreground">No drilldown rows available.</p>}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><ShieldAlert className="h-4 w-4" />Priority Signals</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {summaryEntries.slice(0, 4).map(([label, value]) => (
                <div key={label} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium capitalize">{label.replace(/_/g, " ")}</p>
                    <Badge>{numberValue(value)}</Badge>
                  </div>
                </div>
              ))}
              {!summaryEntries.length && <p className="text-sm text-muted-foreground">No active risk signals for this filter.</p>}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base"><Factory className="h-4 w-4" />Manufacturing Pack</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm">Pack status</span>
                <Badge variant={manufacturingEnabled ? "default" : "secondary"}>{manufacturingEnabled ? "Enabled" : "Disabled"}</Badge>
              </div>
              {!manufacturingEnabled && <Button size="sm" onClick={() => enableManufacturing.mutate()}>Enable Manufacturing</Button>}
              <div className="grid gap-2">
                <Input type="date" value={incident.incident_date} onChange={(e) => setIncident({ ...incident, incident_date: e.target.value })} />
                <Input value={incident.incident_type} onChange={(e) => setIncident({ ...incident, incident_type: e.target.value })} placeholder="Incident type" />
                <Input value={incident.location} onChange={(e) => setIncident({ ...incident, location: e.target.value })} placeholder="Location" />
                <select className="h-10 rounded-md border bg-background px-3 text-sm" value={incident.severity} onChange={(e) => setIncident({ ...incident, severity: e.target.value })}>
                  {["Low", "Medium", "High", "Critical"].map((item) => <option key={item}>{item}</option>)}
                </select>
                <Button size="sm" disabled={!manufacturingEnabled || createIncident.isPending} onClick={() => createIncident.mutate()}>Record Incident</Button>
              </div>
              {(safetyIncidents.data || []).slice(0, 5).map((item) => (
                <div key={item.id} className="rounded-lg border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{item.incident_type}</span>
                    <Badge variant="secondary">{item.severity}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{item.incident_date} {item.location ? `- ${item.location}` : ""}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
