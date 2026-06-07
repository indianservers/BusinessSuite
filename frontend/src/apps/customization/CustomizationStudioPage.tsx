import type React from "react";
import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, FileText, GitBranch, Kanban, LayoutTemplate, ListChecks, Pickaxe, ScrollText, ShieldCheck, SlidersHorizontal, Table2 } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { customizationApi, type CustomizationRecord } from "./api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";

type SectionKey = "modules" | "fields" | "layouts" | "views" | "kanban" | "validation-rules" | "buttons" | "picklists" | "formulas" | "rollups" | "audit";

const sections: Array<{ key: SectionKey; label: string; path: string; icon: typeof Database }> = [
  { key: "modules", label: "Modules", path: "/admin/customization/modules", icon: Database },
  { key: "fields", label: "Fields", path: "/admin/customization/fields", icon: SlidersHorizontal },
  { key: "layouts", label: "Layouts", path: "/admin/customization/layouts", icon: LayoutTemplate },
  { key: "views", label: "Views", path: "/admin/customization/views", icon: Table2 },
  { key: "kanban", label: "Kanban", path: "/admin/customization/kanban", icon: Kanban },
  { key: "validation-rules", label: "Validation", path: "/admin/customization/validation-rules", icon: ShieldCheck },
  { key: "buttons", label: "Buttons", path: "/admin/customization/buttons", icon: Pickaxe },
  { key: "picklists", label: "Picklists", path: "/admin/customization/picklists", icon: ListChecks },
  { key: "formulas", label: "Formulas", path: "/admin/customization/formulas", icon: FileText },
  { key: "rollups", label: "Rollups", path: "/admin/customization/rollups", icon: GitBranch },
  { key: "audit", label: "Audit", path: "/admin/customization/audit", icon: ScrollText },
];

function activeSection(pathname: string): SectionKey {
  return sections.find((item) => pathname.startsWith(item.path))?.key || "modules";
}

export default function CustomizationStudioPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const active = activeSection(location.pathname);
  return (
    <div className="space-y-6">
      <div className="border-b bg-background px-4 py-5 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase text-muted-foreground">Admin</p>
        <h1 className="text-2xl font-semibold">Customization Studio</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">Admin-defined metadata overlays, dynamic forms and records, safe formulas, layouts, views, validation rules, buttons, picklists, rollups, and audit history.</p>
        <div className="mt-4 flex gap-2 overflow-x-auto pb-1">
          {sections.map((item) => {
            const Icon = item.icon;
            return <Button key={item.key} variant={active === item.key ? "default" : "outline"} size="sm" onClick={() => navigate(item.path)}><Icon className="h-4 w-4" />{item.label}</Button>;
          })}
        </div>
      </div>
      <div className="px-4 pb-8 sm:px-6 lg:px-8">
        {active === "modules" ? <Modules /> : null}
        {active === "fields" ? <Fields /> : null}
        {active === "layouts" ? <GenericSection title="Layout Builder" description="Sections, field order, required markers, hidden/read-only placeholders." queryKey="customization-layouts" queryFn={customizationApi.layouts} action="Create Layout" mutation={() => customizationApi.createLayout({ module_name: "partner_projects", name: "Default Detail", layout_type: "detail", is_default: true })} /> : null}
        {active === "views" ? <GenericSection title="List View Builder" description="Saved filters, visible columns, sort order, shared/private and default view metadata." queryKey="customization-views" queryFn={customizationApi.views} action="Create View" mutation={() => customizationApi.createView({ module_name: "partner_projects", name: "Open Projects", filters_json: { status: "open" }, columns_json: ["project_name", "budget"], sort_json: { field: "project_name", direction: "asc" }, shared: true })} /> : null}
        {active === "kanban" ? <GenericSection title="Kanban Builder" description="Group by picklist/status/stage fields with backend transition validation metadata." queryKey="customization-kanban" queryFn={customizationApi.kanban} action="Create Kanban" mutation={() => customizationApi.createKanban({ module_name: "partner_projects", name: "Project Kanban", group_by_field: "status", card_fields_json: ["project_name", "budget"], shared: true })} /> : null}
        {active === "validation-rules" ? <ValidationRules /> : null}
        {active === "buttons" ? <GenericSection title="Custom Buttons" description="Safe configured actions only; no arbitrary script execution." queryKey="customization-buttons" queryFn={customizationApi.buttons} action="Create Button" mutation={() => customizationApi.createButton({ module_name: "partner_projects", label: "Submit Approval", action_type: "submit_approval", action_config_json: { rule: "project_review" } })} /> : null}
        {active === "picklists" ? <GenericSection title="Global Picklists" description="Reusable global value sets for picklist and multi-select fields." queryKey="customization-picklists" queryFn={customizationApi.picklists} action="Create Picklist" mutation={() => customizationApi.createPicklist({ api_name: "project_statuses", label: "Project Statuses", values: [{ value: "open", label: "Open" }, { value: "closed", label: "Closed" }] })} /> : null}
        {active === "formulas" ? <Formulas /> : null}
        {active === "rollups" ? <GenericSection title="Rollup Fields" description="Configured aggregates across related custom records." queryKey="customization-rollups" queryFn={customizationApi.rollups} action="Create Rollup" mutation={() => customizationApi.createRollup({ module_name: "partner_projects", field_api_name: "total_revenue", related_module_name: "partner_invoices", aggregate_function: "sum", aggregate_field: "amount" })} /> : null}
        {active === "audit" ? <GenericSection title="Customization Audit" description="Metadata and dynamic record changes are captured for diagnostics." queryKey="customization-audit" queryFn={customizationApi.audit} /> : null}
      </div>
    </div>
  );
}

function useRefresh(key: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: [key] });
}

function Modules() {
  return <GenericSection title="Module Builder" description="Create admin-defined modules without altering hardcoded CRM, PMS, or SRM modules." queryKey="customization-modules" queryFn={customizationApi.modules} action="Create Module" mutation={() => customizationApi.createModule({ module_api_name: "partner_projects", module_label: "Partner Project", plural_label: "Partner Projects", icon: "database", description: "Partner delivery records", enabled: true })} />;
}

function Fields() {
  return <GenericSection title="Field Builder" description="Required, unique, typed, picklist, lookup, formula, rollup, visibility, and editability metadata." queryKey="customization-fields" queryFn={customizationApi.fields} action="Create Field" mutation={() => customizationApi.createField({ module_name: "partner_projects", field_api_name: "project_name", field_label: "Project Name", field_type: "text", required: true, unique: true, visible: true, editable: true })} />;
}

function ValidationRules() {
  return <GenericSection title="Validation Rules" description="Backend-enforced safe JSON validation rules." queryKey="customization-validation" queryFn={customizationApi.validationRules} action="Create Rule" mutation={() => customizationApi.createValidationRule({ module_name: "partner_projects", name: "Budget must be positive", condition_json: { field: "budget", operator: "less_or_equal", value: 0 }, error_message: "Budget must be greater than zero", active: true })} />;
}

function Formulas() {
  const { toast } = useToast();
  const query = useQuery({ queryKey: ["customization-formulas"], queryFn: customizationApi.formulas });
  const refresh = useRefresh("customization-formulas");
  const create = useMutation({
    mutationFn: () => customizationApi.createFormula({ module_name: "partner_projects", field_api_name: "margin", expression: "revenue - cost", return_type: "decimal" }),
    onSuccess: () => { toast({ title: "Formula saved" }); refresh(); },
  });
  const testFormula = useMutation({
    mutationFn: () => customizationApi.testFormula({ expression: "revenue - cost", record: { revenue: 1000, cost: 250 } }),
    onSuccess: (data) => toast({ title: `Formula result ${data.result}` }),
  });
  return <SectionFrame title="Formula Fields" description="AST-validated formula expressions with a safe tester." action="Create Formula" onAction={() => create.mutate()} query={query}><Button variant="outline" onClick={() => testFormula.mutate()}>Test Formula</Button></SectionFrame>;
}

function GenericSection({ title, description, queryKey, queryFn, action, mutation }: { title: string; description: string; queryKey: string; queryFn: () => Promise<{ items: CustomizationRecord[]; total: number }>; action?: string; mutation?: () => Promise<unknown> }) {
  const { toast } = useToast();
  const query = useQuery({ queryKey: [queryKey], queryFn });
  const refresh = useRefresh(queryKey);
  const create = useMutation({ mutationFn: mutation || (() => Promise.resolve()), onSuccess: () => { toast({ title: `${title.split(" ")[0]} saved` }); refresh(); } });
  return <SectionFrame title={title} description={description} action={action} onAction={action ? () => create.mutate() : undefined} query={query} />;
}

function SectionFrame({ title, description, action, onAction, query, children }: { title: string; description: string; action?: string; onAction?: () => void; query: ReturnType<typeof useQuery<{ items: CustomizationRecord[]; total: number }>>; children?: React.ReactNode }) {
  const items = useMemo(() => query.data?.items || [], [query.data]);
  return (
    <div className="space-y-4">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div><h2 className="text-lg font-semibold">{title}</h2><p className="text-sm text-muted-foreground">{description}</p></div>
        <div className="flex gap-2">{children}{action ? <Button onClick={onAction}>{action}</Button> : null}</div>
      </div>
      {query.isLoading ? <div className="rounded-md border bg-card px-4 py-3 text-sm text-muted-foreground">Loading customization metadata...</div> : null}
      {query.isError ? <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">Customization metadata could not be loaded.</div> : null}
      {!query.isLoading && !items.length ? <div className="rounded-md border bg-card px-4 py-6 text-sm text-muted-foreground">No records configured yet.</div> : null}
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item) => <Card key={String(item.id)}><CardContent className="flex items-start justify-between gap-3 p-4"><div><p className="font-medium">{String(item.name || item.module_label || item.field_label || item.label || item.entity_type || `Record ${item.id}`)}</p><p className="mt-1 text-xs text-muted-foreground">{String(item.module_name || item.module_api_name || item.field_type || item.action || "customization")}</p></div><Badge variant="outline">{String(item.enabled ?? item.active ?? item.visible ?? "ready")}</Badge></CardContent></Card>)}
      </div>
    </div>
  );
}
