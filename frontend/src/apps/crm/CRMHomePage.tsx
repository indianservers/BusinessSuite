import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, Building2, CheckCircle2, Kanban, Plus, Users } from "lucide-react";
import { crmApi, type CRMApiRecord } from "./api";
import { api } from "@/services/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const metrics = [
  { label: "Leads", value: "Ready", icon: Users },
  { label: "Pipeline", value: "Ready", icon: Kanban },
  { label: "Reports", value: "Planned", icon: BarChart3 },
];

type CRMModuleInfo = {
  key: string;
  name: string;
  status: string;
  modules: string[];
};

type QuickCreateType = "leads" | "contacts" | "companies" | "deals" | "tasks";

type QuickCreateField = {
  key: string;
  label: string;
  type?: string;
  required?: boolean;
  placeholder?: string;
};

const quickCreateTypes: Array<{ value: QuickCreateType; label: string; description: string }> = [
  { value: "leads", label: "Lead", description: "Capture a new prospect." },
  { value: "contacts", label: "Contact", description: "Add a person to CRM." },
  { value: "companies", label: "Company", description: "Create an account record." },
  { value: "deals", label: "Deal", description: "Start a pipeline opportunity." },
  { value: "tasks", label: "Task", description: "Create a CRM follow-up task." },
];

const quickCreateFields: Record<QuickCreateType, QuickCreateField[]> = {
  leads: [
    { key: "name", label: "Lead name", required: true, placeholder: "Jane Shah" },
    { key: "company", label: "Company", placeholder: "Acme India" },
    { key: "email", label: "Email", type: "email", placeholder: "jane@company.com" },
    { key: "phone", label: "Phone", placeholder: "+919876543210" },
    { key: "source", label: "Source", placeholder: "Website" },
  ],
  contacts: [
    { key: "name", label: "Contact name", required: true, placeholder: "Jane Shah" },
    { key: "email", label: "Email", type: "email", placeholder: "jane@company.com" },
    { key: "phone", label: "Phone", placeholder: "+919876543210" },
    { key: "source", label: "Source", placeholder: "Referral" },
  ],
  companies: [
    { key: "name", label: "Company name", required: true, placeholder: "Acme India" },
    { key: "industry", label: "Industry", placeholder: "Software" },
    { key: "email", label: "Email", type: "email", placeholder: "hello@company.com" },
    { key: "phone", label: "Phone", placeholder: "+919876543210" },
  ],
  deals: [
    { key: "name", label: "Deal name", required: true, placeholder: "ERP rollout" },
    { key: "amount", label: "Amount", type: "number", placeholder: "500000" },
    { key: "expectedCloseDate", label: "Expected close", type: "date" },
  ],
  tasks: [
    { key: "title", label: "Task title", required: true, placeholder: "Call lead" },
    { key: "dueDate", label: "Due date", type: "date" },
    { key: "priority", label: "Priority", placeholder: "Medium" },
  ],
};

const emptyQuickDraft: Record<string, string> = {
  name: "",
  company: "",
  email: "",
  phone: "",
  source: "",
  industry: "",
  amount: "",
  expectedCloseDate: "",
  title: "",
  dueDate: "",
  priority: "Medium",
};

export default function CRMHomePage() {
  const navigate = useNavigate();
  const [moduleInfo, setModuleInfo] = useState<CRMModuleInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quickType, setQuickType] = useState<QuickCreateType>("leads");
  const [quickDraft, setQuickDraft] = useState<Record<string, string>>(emptyQuickDraft);
  const [quickSaving, setQuickSaving] = useState(false);
  const [quickMessage, setQuickMessage] = useState<string | null>(null);
  const [quickError, setQuickError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<CRMModuleInfo>("/crm/module-info")
      .then((response) => setModuleInfo(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "CRM backend is not reachable."));
  }, []);

  const patchQuickDraft = (key: string, value: string) => {
    setQuickDraft((current) => ({ ...current, [key]: value }));
    setQuickMessage(null);
    setQuickError(null);
  };

  const createQuickRecord = async () => {
    setQuickSaving(true);
    setQuickError(null);
    setQuickMessage(null);
    try {
      const payload = await buildQuickCreatePayload(quickType, quickDraft);
      const response = await crmApi.create<CRMApiRecord>(quickType, payload);
      const id = response.data?.id;
      const label = quickCreateTypes.find((item) => item.value === quickType)?.label || "Record";
      setQuickDraft(emptyQuickDraft);
      setQuickMessage(`${label} created successfully.`);
      if (id && quickType !== "tasks") {
        navigate(`/crm/${quickType}/${id}`);
      } else {
        navigate(`/crm/${quickType}`);
      }
    } catch (err: unknown) {
      const detail = getApiErrorDetail(err);
      setQuickError(detail || "CRM record could not be created.");
    } finally {
      setQuickSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-emerald-100 p-3 text-emerald-700">
              <Building2 className="h-6 w-6" />
            </div>
            <div>
              <h1 className="page-title">VyaparaCRM</h1>
              <p className="page-description">Leads, contacts, companies, deals, activities, quotations, campaigns, and support.</p>
            </div>
          </div>
        </div>
        <Badge className={moduleInfo?.status === "installed" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}>
          {moduleInfo?.status || "checking"}
        </Badge>
      </div>

      {error ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}

      <div className="grid gap-4 md:grid-cols-3">
        {metrics.map((metric) => (
          <Card key={metric.label}>
            <CardContent className="flex items-center gap-4 p-5">
              <div className="rounded-lg bg-emerald-100 p-3 text-emerald-700">
                <metric.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{metric.label}</p>
                <p className="text-xl font-semibold">{metric.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="space-y-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle>Quick Create</CardTitle>
              <p className="mt-1 text-sm text-muted-foreground">Create CRM records directly from the home page using the shared CRM backend.</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {quickCreateTypes.map((item) => (
                <Button
                  key={item.value}
                  type="button"
                  size="sm"
                  variant={quickType === item.value ? "default" : "outline"}
                  onClick={() => {
                    setQuickType(item.value);
                    setQuickDraft(emptyQuickDraft);
                    setQuickError(null);
                    setQuickMessage(null);
                  }}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          </div>
          <p className="text-sm text-muted-foreground">{quickCreateTypes.find((item) => item.value === quickType)?.description}</p>
        </CardHeader>
        <CardContent className="space-y-4">
          {quickError ? <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{quickError}</div> : null}
          {quickMessage ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">{quickMessage}</div> : null}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {quickCreateFields[quickType].map((field) => (
              <div key={field.key} className="space-y-2">
                <Label htmlFor={`quick-${field.key}`}>
                  {field.label}
                  {field.required ? <span className="text-red-600"> *</span> : null}
                </Label>
                <Input
                  id={`quick-${field.key}`}
                  type={field.type || "text"}
                  value={quickDraft[field.key] || ""}
                  placeholder={field.placeholder}
                  onChange={(event) => patchQuickDraft(field.key, event.target.value)}
                />
              </div>
            ))}
          </div>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted-foreground">Required fields are validated by the existing CRM API.</p>
            <Button type="button" onClick={createQuickRecord} disabled={quickSaving || !isQuickCreateReady(quickType, quickDraft)}>
              <Plus className="h-4 w-4" />
              {quickSaving ? "Creating..." : `Create ${quickCreateTypes.find((item) => item.value === quickType)?.label}`}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Shared CRM Backend Modules</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
          {(moduleInfo?.modules || ["leads", "contacts", "companies", "deals", "pipelines", "activities"]).map((module) => (
            <div key={module} className="flex items-center gap-2 rounded-lg border bg-card p-3 text-sm">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span className="capitalize">{module.replace(/-/g, " ")}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function splitName(value: string) {
  const name = value.trim();
  const [firstName, ...rest] = name.split(/\s+/);
  return {
    firstName: firstName || name,
    lastName: rest.join(" "),
    fullName: name,
  };
}

async function buildQuickCreatePayload(type: QuickCreateType, draft: Record<string, string>): Promise<CRMApiRecord> {
  const today = new Date().toISOString().slice(0, 10);
  if (type === "leads") {
    const name = splitName(draft.name);
    return {
      first_name: name.firstName,
      last_name: name.lastName,
      full_name: name.fullName,
      company_name: draft.company || undefined,
      email: draft.email || undefined,
      phone: draft.phone || undefined,
      source: draft.source || "Manual Entry",
      status: "New",
    };
  }
  if (type === "contacts") {
    const name = splitName(draft.name);
    return {
      first_name: name.firstName,
      last_name: name.lastName,
      full_name: name.fullName,
      email: draft.email || undefined,
      phone: draft.phone || undefined,
      source: draft.source || "Manual Entry",
      status: "Active",
    };
  }
  if (type === "companies") {
    return {
      name: draft.name.trim(),
      industry: draft.industry || undefined,
      email: draft.email || undefined,
      phone: draft.phone || undefined,
      status: "Active",
      account_type: "Prospect",
    };
  }
  if (type === "deals") {
    const pipeline = await crmApi.list<CRMApiRecord>("pipelines", { page: 1, per_page: 1 });
    const pipelineId = Number(pipeline.data.items?.[0]?.id || 1);
    const stages = await crmApi.list<CRMApiRecord>("pipeline-stages", { page: 1, per_page: 1, pipeline_id: pipelineId });
    const stageId = Number(stages.data.items?.[0]?.id || 1);
    return {
      name: draft.name.trim(),
      pipeline_id: pipelineId,
      stage_id: stageId,
      amount: Number(draft.amount || 0),
      probability: 10,
      status: "Open",
      expected_close_date: draft.expectedCloseDate || today,
    };
  }
  return {
    title: draft.title.trim(),
    description: draft.name || undefined,
    due_date: draft.dueDate || today,
    priority: draft.priority || "Medium",
    status: "Open",
  };
}

function isQuickCreateReady(type: QuickCreateType, draft: Record<string, string>) {
  if (type === "tasks") return Boolean(draft.title?.trim());
  return Boolean(draft.name?.trim());
}

function getApiErrorDetail(err: unknown) {
  const response = (err as { response?: { data?: { detail?: unknown } } })?.response;
  const detail = response?.data?.detail;
  if (Array.isArray(detail)) return detail.map((item) => String((item as { msg?: string }).msg || JSON.stringify(item))).join("; ");
  if (typeof detail === "string") return detail;
  if (detail) return JSON.stringify(detail);
  return null;
}
