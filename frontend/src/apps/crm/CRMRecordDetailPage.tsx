import { useEffect, useMemo, useState, type ChangeEvent, type KeyboardEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  Activity,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock,
  Download,
  Edit3,
  FileCheck2,
  FileText,
  GitMerge,
  Mail,
  MessageSquare,
  Phone,
  Plus,
  Save,
  Sparkles,
  Trash2,
  UserRound,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { formatCurrency, formatDate, statusColor } from "@/lib/utils";
import AskAiButton from "@/components/ai-agents/AskAiButton";
import { communicationApi } from "@/apps/communication/api";
import { crmApi, type CRMApiRecord, type CRMApiValue, type CRMApprovalRequest, type CRMEnrichmentPreview } from "./api";

type DetailKind = "leads" | "contacts" | "accounts" | "deals" | "quotations";
type DetailRecord = Record<string, any> & {
  related?: Record<string, unknown>;
  timeline?: TimelineEvent[];
  customFields?: CustomFieldDetail[];
};
type TimelineEvent = { type?: string; title?: string; occurredAt?: string; record?: CRMApiRecord };
type CustomFieldDetail = CRMApiRecord & { value?: unknown; valueRecord?: CRMApiRecord };
type MentionUser = CRMApiRecord & { id: number; displayName?: string; email?: string };
type QuickAction = "note" | "task" | "call" | "email" | "meeting" | "quotation";
type InlineFieldType = "text" | "number" | "date" | "datetime" | "select" | "tags";
type DetailInlineConfig = { type: InlineFieldType; apiField?: string; options?: string[] };

const detailConfig: Record<DetailKind, { entity: string; listPath: string; label: string; singular: string; nameKeys: string[]; statusKeys: string[]; keyFields: string[] }> = {
  leads: {
    entity: "leads",
    listPath: "/crm/leads",
    label: "Leads",
    singular: "Lead",
    nameKeys: ["full_name", "name", "email"],
    statusKeys: ["status", "lead_score_label"],
    keyFields: ["full_name", "company_name", "email", "phone", "source", "status", "territory_id", "lead_score", "lead_score_label", "lead_score_mode", "estimated_value", "next_follow_up_at"],
  },
  contacts: {
    entity: "contacts",
    listPath: "/crm/contacts",
    label: "Contacts",
    singular: "Contact",
    nameKeys: ["full_name", "name", "email"],
    statusKeys: ["status", "lifecycle_stage"],
    keyFields: ["full_name", "email", "phone", "job_title", "department", "lifecycle_stage", "status", "next_follow_up_at"],
  },
  accounts: {
    entity: "companies",
    listPath: "/crm/companies",
    label: "Accounts",
    singular: "Account",
    nameKeys: ["name", "email"],
    statusKeys: ["status", "account_type"],
    keyFields: ["name", "industry", "account_type", "status", "territory_id", "email", "phone", "city", "annual_revenue"],
  },
  deals: {
    entity: "deals",
    listPath: "/crm/deals",
    label: "Deals",
    singular: "Deal",
    nameKeys: ["name"],
    statusKeys: ["status", "stage_id"],
    keyFields: ["name", "amount", "currency", "probability", "status", "territory_id", "expected_close_date", "company_id", "contact_id", "pipeline_id", "stage_id"],
  },
  quotations: {
    entity: "quotations",
    listPath: "/crm/quotations",
    label: "Quotations",
    singular: "Quotation",
    nameKeys: ["quote_number"],
    statusKeys: ["status"],
    keyFields: ["quote_number", "status", "issue_date", "expiry_date", "subtotal", "discount_amount", "tax_amount", "total_amount", "deal_id", "company_id", "contact_id"],
  },
};

const readOnlyKeys = new Set(["id", "organization_id", "organizationId", "created_at", "createdAt", "created_by_user_id", "createdBy", "updated_at", "updatedAt", "updated_by_user_id", "updatedBy", "deleted_at", "deletedAt", "entity", "related", "timeline", "customFields"]);

const detailInlineEditConfig: Record<DetailKind, Record<string, DetailInlineConfig>> = {
  leads: {
    full_name: { type: "text" },
    company_name: { type: "text" },
    email: { type: "text" },
    phone: { type: "text" },
    source: { type: "select", options: ["Website", "Referral", "Event", "Partner", "Phone Call", "Email Campaign", "Other"] },
    status: { type: "select", options: ["New", "Contacted", "Qualified", "Converted", "Lost"] },
    rating: { type: "select", options: ["Hot", "Warm", "Cold"] },
    lead_score: { type: "number" },
    lead_score_mode: { type: "select", options: ["automatic", "manual"] },
    estimated_value: { type: "number" },
    expected_close_date: { type: "date" },
    next_follow_up_at: { type: "datetime" },
    owner_user_id: { type: "number", apiField: "ownerId" },
    territory_id: { type: "number", apiField: "territoryId" },
    tags_text: { type: "tags" },
  },
  contacts: {
    full_name: { type: "text" },
    email: { type: "text" },
    phone: { type: "text" },
    job_title: { type: "text" },
    department: { type: "text" },
    lifecycle_stage: { type: "select", options: ["Lead", "Opportunity", "Customer", "Inactive"] },
    status: { type: "select", options: ["Active", "Open", "Inactive"] },
    next_follow_up_at: { type: "datetime" },
    owner_user_id: { type: "number", apiField: "ownerId" },
    territory_id: { type: "number", apiField: "territoryId" },
    tags_text: { type: "tags" },
  },
  accounts: {
    name: { type: "text" },
    industry: { type: "text" },
    account_type: { type: "select", options: ["Prospect", "Customer", "Partner", "Vendor"] },
    status: { type: "select", options: ["Active", "Inactive", "Prospect"] },
    email: { type: "text" },
    phone: { type: "text" },
    city: { type: "text" },
    annual_revenue: { type: "number" },
    owner_user_id: { type: "number", apiField: "ownerId" },
    territory_id: { type: "number", apiField: "territoryId" },
    tags_text: { type: "tags" },
  },
  deals: {
    name: { type: "text" },
    amount: { type: "number" },
    probability: { type: "number" },
    status: { type: "select", options: ["Open", "Won", "Lost"] },
    expected_close_date: { type: "date" },
    stage_id: { type: "number" },
    owner_user_id: { type: "number", apiField: "ownerId" },
    territory_id: { type: "number", apiField: "territoryId" },
    tags_text: { type: "tags" },
  },
  quotations: {
    quote_number: { type: "text" },
    status: { type: "select", options: ["Draft", "Sent", "Accepted", "Rejected", "Expired"] },
    issue_date: { type: "date" },
    expiry_date: { type: "date" },
    subtotal: { type: "number" },
    discount_amount: { type: "number" },
    tax_amount: { type: "number" },
    total_amount: { type: "number" },
    owner_user_id: { type: "number", apiField: "ownerId" },
  },
};

export default function CRMRecordDetailPage({ kind }: { kind: DetailKind }) {
  const { id } = useParams();
  const navigate = useNavigate();
  const config = detailConfig[kind];
  const recordId = Number(id);
  const [record, setRecord] = useState<DetailRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [action, setAction] = useState<QuickAction | null>(null);
  const [enrichmentOpen, setEnrichmentOpen] = useState(false);
  const [messageOpen, setMessageOpen] = useState(false);
  const [approvalSubmitting, setApprovalSubmitting] = useState(false);
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [leadConverting, setLeadConverting] = useState(false);

  const loadRecord = () => {
    setLoading(true);
    setError(null);
    crmApi
      .get<DetailRecord>(config.entity, recordId)
      .then((response) => setRecord(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "CRM record could not be loaded."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRecord();
  }, [config.entity, recordId]);

  const title = useMemo(() => titleFor(record, config.nameKeys, config.singular), [record, config]);
  const statusBadges = config.statusKeys.map((key) => valueText(record?.[key])).filter(Boolean);
  const approval = approvalFor(record);
  const approvalStatus = valueText(approval?.status);
  const finalActionBlocked = approvalStatus === "pending" || approvalStatus === "rejected";
  const duplicateCount = duplicateCountFor(record);
  const aiContext = getAiContext(kind);

  const updateRecord = (data: CRMApiRecord) => {
    setSaving(true);
    setError(null);
    return crmApi
      .update<DetailRecord>(config.entity, recordId, data)
      .then((response) => {
        setRecord(response.data);
        setEditOpen(false);
      })
      .catch((err) => setError(err?.response?.data?.detail || "CRM record could not be saved."))
      .finally(() => setSaving(false));
  };

  const saveInlineField = (key: string, value: string | number | boolean | null) => {
    if (!record) return Promise.resolve();
    const configItem = detailInlineEditConfig[kind]?.[key];
    if (!configItem) return Promise.resolve();
    const previous = record;
    const next = { ...record, [key]: value } as DetailRecord;
    setRecord(next);
    setSaving(true);
    setError(null);
    return crmApi
      .update<DetailRecord>(config.entity, recordId, { [configItem.apiField || key]: normalizeDetailInlineValue(configItem, value) })
      .then((response) => setRecord(response.data))
      .catch((err) => {
        setRecord(previous);
        throw new Error(err?.response?.data?.detail || "CRM record could not be saved.");
      })
      .finally(() => setSaving(false));
  };

  const saveCustomField = (field: CustomFieldDetail, value: string | number | boolean | null) => {
    if (!record) return Promise.resolve();
    const previous = record;
    const customFields = (record.customFields || []).map((item) => (Number(item.id) === Number(field.id) ? { ...item, value } : item)) as CustomFieldDetail[];
    setRecord({ ...record, customFields } as DetailRecord);
    return crmApi
      .upsertCustomFieldValue({
        customFieldId: Number(field.id),
        entity: String(field.entity || config.entity),
        recordId,
        value,
      })
      .then((response) => {
        setRecord((current) => {
          if (!current) return current;
          return {
            ...current,
            customFields: (current.customFields || []).map((item) =>
              Number(item.id) === Number(field.id) ? { ...item, value: response.data.value as CRMApiValue, valueRecord: response.data } : item,
            ),
          } as DetailRecord;
        });
      })
      .catch((err) => {
        setRecord(previous);
        throw new Error(err?.response?.data?.detail || "Custom field could not be saved.");
      });
  };

  const deleteRecord = () => {
    if (!window.confirm(`Delete this ${config.singular.toLowerCase()}?`)) return;
    crmApi.delete(config.entity, recordId).then(() => navigate(config.listPath)).catch((err) => setError(err?.response?.data?.detail || "CRM record could not be deleted."));
  };

  const recalculateScore = () => {
    if (kind !== "leads") return;
    setSaving(true);
    setError(null);
    crmApi.recalculateLeadScore<DetailRecord>(recordId)
      .then((response) => setRecord(response.data))
      .catch((err) => setError(err?.response?.data?.detail || "Lead score could not be recalculated."))
      .finally(() => setSaving(false));
  };

  const convertLead = () => {
    if (kind !== "leads") return;
    setLeadConverting(true);
    setError(null);
    crmApi
      .convertLead<{ lead: DetailRecord; contact?: CRMApiRecord | null; company?: CRMApiRecord | null; deal?: CRMApiRecord | null }>(recordId, {
        createContact: true,
        createCompany: true,
        createDeal: true,
      })
      .then((response) => {
        setRecord(response.data.lead);
        const dealId = response.data.deal?.id;
        const contactId = response.data.contact?.id;
        if (dealId) navigate(`/crm/deals/${dealId}`);
        else if (contactId) navigate(`/crm/contacts/${contactId}`);
      })
      .catch((err) => setError(err?.response?.data?.detail || "Lead could not be converted."))
      .finally(() => setLeadConverting(false));
  };

  const submitApproval = () => {
    if (!record || !["deals", "quotations"].includes(kind)) return;
    setApprovalSubmitting(true);
    setError(null);
    crmApi
      .submitApproval({ entityType: kind === "deals" ? "deal" : "quotation", entityId: recordId, triggerType: "manual" })
      .then(loadRecord)
      .catch((err) => setError(err?.response?.data?.detail || "Approval could not be submitted."))
      .finally(() => setApprovalSubmitting(false));
  };

  const openQuotationPdf = (download = false) => {
    if (kind !== "quotations") return;
    setPdfGenerating(true);
    setError(null);
    crmApi
      .quotationPdf(recordId, download)
      .then((response) => {
        const blob = new Blob([response.data], { type: "application/pdf" });
        const url = window.URL.createObjectURL(blob);
        if (download) {
          const link = document.createElement("a");
          link.href = url;
          link.download = `${valueText(record?.quote_number) || `quotation-${recordId}`}.pdf`;
          document.body.appendChild(link);
          link.click();
          link.remove();
          window.setTimeout(() => window.URL.revokeObjectURL(url), 1000);
        } else {
          window.open(url, "_blank", "noopener,noreferrer");
          window.setTimeout(() => window.URL.revokeObjectURL(url), 30000);
        }
        loadRecord();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Quotation PDF could not be generated."))
      .finally(() => setPdfGenerating(false));
  };

  return (
    <div className="space-y-5">
      <nav className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Link to="/crm" className="hover:text-foreground">CRM</Link>
        <ChevronRight className="h-4 w-4" />
        <Link to={config.listPath} className="hover:text-foreground">{config.label}</Link>
        <ChevronRight className="h-4 w-4" />
        <span className="text-foreground">{title}</span>
      </nav>

      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div> : null}
      {loading ? <div className="rounded-md border bg-card px-4 py-8 text-center text-sm text-muted-foreground">Loading {config.singular.toLowerCase()} details...</div> : null}

      {!loading && record ? (
        <>
          <header className="rounded-lg border bg-card p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="truncate text-2xl font-semibold">{title}</h1>
                  {statusBadges.map((status) => <Badge key={status} className={statusColor(status)}>{status}</Badge>)}
                  {approvalStatus ? <Badge className={statusColor(approvalStatus)}>Approval {labelFor(approvalStatus)}</Badge> : null}
                  {kind === "quotations" ? <Badge className={statusColor(valueText(record.pdfStatus || record.pdf_status) || "not generated")}>PDF {labelFor(valueText(record.pdfStatus || record.pdf_status) || "not generated")}</Badge> : null}
                  {duplicateCount ? <Badge className="bg-amber-100 text-amber-800"><GitMerge className="mr-1 h-3.5 w-3.5" />{duplicateCount} possible duplicate{duplicateCount === 1 ? "" : "s"}</Badge> : null}
                </div>
                <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1"><UserRound className="h-4 w-4" />Owner {valueText(record.ownerId || record.owner_user_id) || "Unassigned"}</span>
                  <span>Last updated {formatDate(valueText(record.updatedAt || record.updated_at || record.createdAt || record.created_at))}</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <AskAiButton
                  module="CRM"
                  relatedEntityType={aiContext.entityType}
                  relatedEntityId={recordId}
                  defaultAgentCode={aiContext.agentCode}
                  defaultPrompt={aiContext.prompt}
                />
                <Button variant="outline" onClick={() => setEditOpen(true)}><Edit3 className="h-4 w-4" />Edit</Button>
                <Button variant="outline" onClick={() => setAction("note")}><Plus className="h-4 w-4" />Add Note</Button>
                <Button variant="outline" onClick={() => setAction("task")}><CalendarDays className="h-4 w-4" />Add Task</Button>
                <Button variant="outline" onClick={() => setAction("call")}><Phone className="h-4 w-4" />Add Call</Button>
                <Button variant="outline" onClick={() => setAction("email")}><Mail className="h-4 w-4" />Send Email</Button>
                {["leads", "contacts", "deals"].includes(kind) ? <Button variant="outline" onClick={() => setMessageOpen(true)}><MessageSquare className="h-4 w-4" />Send SMS/WhatsApp</Button> : null}
                {["leads", "contacts"].includes(kind) ? <Button variant="outline" onClick={() => setEnrichmentOpen(true)}><Sparkles className="h-4 w-4" />Enrich Contact</Button> : null}
                {kind === "leads" ? <Button variant="outline" onClick={recalculateScore} disabled={saving}><CheckCircle2 className="h-4 w-4" />Recalculate Score</Button> : null}
                {kind === "leads" ? <Button variant="outline" onClick={convertLead} disabled={leadConverting || Boolean(record.is_converted)}><FileCheck2 className="h-4 w-4" />{leadConverting ? "Converting..." : "Convert Lead"}</Button> : null}
                {["deals", "quotations"].includes(kind) ? <Button variant="outline" onClick={submitApproval} disabled={approvalSubmitting || approvalStatus === "pending"}><FileCheck2 className="h-4 w-4" />{approvalSubmitting ? "Submitting..." : "Submit Approval"}</Button> : null}
                {kind === "quotations" ? <Button variant="outline" onClick={() => openQuotationPdf(false)} disabled={pdfGenerating}><FileText className="h-4 w-4" />{pdfGenerating ? "Generating..." : "Generate PDF"}</Button> : null}
                {kind === "quotations" ? <Button variant="outline" onClick={() => openQuotationPdf(true)} disabled={pdfGenerating}><Download className="h-4 w-4" />Download PDF</Button> : null}
                {kind !== "quotations" ? <Button variant="outline" onClick={() => setAction("quotation")}><FileText className="h-4 w-4" />Create Quotation</Button> : null}
                <Button variant="destructive" onClick={deleteRecord}><Trash2 className="h-4 w-4" />Delete</Button>
              </div>
            </div>
          </header>

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_25rem]">
            <main className="space-y-5">
              <DetailFields kind={kind} record={record} fields={config.keyFields} onSave={saveInlineField} saving={saving} />
              {kind === "deals" ? <CommercialHandoff related={record.related || {}} /> : null}
              <FullDetails kind={kind} record={record} onSave={saveInlineField} />
              {["deals", "quotations"].includes(kind) ? <ApprovalTimeline approval={approval} /> : null}
              <CustomFields fields={record.customFields || []} onSave={saveCustomField} />
            </main>
            <aside className="space-y-5">
              <AICopilotPanel kind={kind} recordId={recordId} />
              <CommunicationTimeline recordType={kind === "accounts" ? "account" : kind.replace(/s$/, "")} recordId={recordId} />
              <Timeline events={record.timeline || []} onAction={setAction} />
              <RelatedRecords related={record.related || {}} />
            </aside>
          </div>
        </>
      ) : null}

      {editOpen && record ? <EditRecordModal record={record} title={`Edit ${config.singular}`} saving={saving} onClose={() => setEditOpen(false)} onSave={updateRecord} /> : null}
      {enrichmentOpen && record ? <EnrichmentModal kind={kind} record={record} recordId={recordId} onClose={() => setEnrichmentOpen(false)} onDone={(next) => { setRecord(next); setEnrichmentOpen(false); loadRecord(); }} /> : null}
      {messageOpen && record ? <MessageComposeModal kind={kind} record={record} onClose={() => setMessageOpen(false)} onDone={() => { setMessageOpen(false); loadRecord(); }} /> : null}
      {action === "email" && record ? <EmailComposeModal kind={kind} record={record} disabled={finalActionBlocked} approvalStatus={approvalStatus} onClose={() => setAction(null)} onDone={() => { setAction(null); loadRecord(); }} /> : null}
      {action && action !== "email" && record ? <QuickActionModal action={action} kind={kind} record={record} entity={config.entity} recordId={recordId} onClose={() => setAction(null)} onDone={() => { setAction(null); loadRecord(); }} /> : null}
    </div>
  );
}

function DetailFields({ kind, record, fields, onSave, saving }: { kind: DetailKind; record: DetailRecord; fields: string[]; onSave: (key: string, value: string | number | boolean | null) => Promise<unknown>; saving: boolean }) {
  return (
    <Card>
      <CardHeader><CardTitle>Key Fields</CardTitle></CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2">
        {fields.map((key) => <InlineField key={key} config={detailInlineEditConfig[kind]?.[key]} fieldKey={key} value={record[key]} onSave={onSave} saving={saving} />)}
      </CardContent>
    </Card>
  );
}

function CommercialHandoff({ related }: { related: Record<string, unknown> }) {
  const srm = related.srm as CRMApiRecord | undefined;
  if (!srm || typeof srm !== "object") return null;
  const salesOrder = srm.salesOrder as CRMApiRecord | null | undefined;
  const engagement = srm.engagement as CRMApiRecord | null | undefined;
  const contract = srm.contract as CRMApiRecord | null | undefined;
  const billingPlan = srm.billingPlan as CRMApiRecord | null | undefined;
  const pmsProject = srm.pmsProject as CRMApiRecord | null | undefined;
  return (
    <Card>
      <CardHeader><CardTitle>Commercial Handoff</CardTitle></CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2">
        <HandoffLine label="SRM Sales Order" value={valueText(salesOrder?.order_number || salesOrder?.title)} to={salesOrder?.id ? `/srm/sales-orders` : undefined} />
        <HandoffLine label="SRM Engagement" value={valueText(engagement?.engagement_number || engagement?.name)} to={engagement?.id ? `/srm/engagements` : undefined} />
        <HandoffLine label="SRM Contract" value={valueText(contract?.contract_number || contract?.title)} to={contract?.id ? `/srm/contracts` : undefined} />
        <HandoffLine label="Billing Plan" value={valueText(billingPlan?.name || billingPlan?.billing_type)} to={billingPlan?.id ? `/srm/billing-plans` : undefined} />
        <HandoffLine label="PMS Project" value={valueText(pmsProject?.project_key || pmsProject?.name)} to={pmsProject?.id ? `/pms/projects/${pmsProject.id}` : undefined} />
      </CardContent>
    </Card>
  );
}

function AICopilotPanel({ kind, recordId }: { kind: DetailKind; recordId: number }) {
  const recordType = kind === "accounts" ? "account" : kind === "quotations" ? "quotation" : kind.replace(/s$/, "");
  const summaryHref = `/ai/record-summary?module_name=crm&record_type=${recordType}&record_id=${recordId}`;
  const coachHref = kind === "deals" ? `/ai/deal-coach?module_name=crm&record_type=deal&record_id=${recordId}` : `/ai/copilot?module_name=crm&record_type=${recordType}&record_id=${recordId}`;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base"><Sparkles className="h-4 w-4" />AI Copilot Panel</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-sm text-muted-foreground">Uses sanitized CRM context and backend AI permissions for this record.</p>
        <div className="flex flex-wrap gap-2">
          <Button asChild variant="outline" size="sm"><Link to={summaryHref}>Record Summary</Link></Button>
          <Button asChild variant="outline" size="sm"><Link to={coachHref}>{kind === "deals" ? "Deal Coach" : "Open Copilot"}</Link></Button>
        </div>
      </CardContent>
    </Card>
  );
}

function HandoffLine({ label, value, to }: { label: string; value: string; to?: string }) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <p className="text-xs font-medium uppercase text-muted-foreground">{label}</p>
      {to && value ? <Link to={to} className="mt-1 block truncate font-medium text-primary hover:underline">{value}</Link> : <p className="mt-1 font-medium">{value || "Not linked"}</p>}
    </div>
  );
}

function InlineField({ fieldKey, value, config, onSave, saving }: { fieldKey: string; value: unknown; config?: DetailInlineConfig; onSave: (key: string, value: string | number | boolean | null) => Promise<unknown>; saving: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(valueText(value));
  const [error, setError] = useState<string | null>(null);
  useEffect(() => setDraft(valueText(value)), [value]);
  const commit = () => {
    if (!config || draft === valueText(value)) {
      setEditing(false);
      return;
    }
    setError(null);
    onSave(fieldKey, draft)
      .then(() => setEditing(false))
      .catch((err) => {
        setDraft(valueText(value));
        setError(err?.message || "Could not save.");
      });
  };
  return (
    <div className="group rounded-md border bg-muted/25 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{labelFor(fieldKey)}</p>
      {editing ? (
        <div className="mt-2 space-y-1">
          <div className="flex gap-2">
            <DetailInlineEditor config={config || { type: "text" }} value={draft} onChange={setDraft} onCommit={commit} onCancel={() => { setDraft(valueText(value)); setEditing(false); setError(null); }} />
            <Button size="sm" onClick={commit} disabled={saving}><Save className="h-4 w-4" /></Button>
          </div>
          {error ? <p className="text-xs text-destructive">{error}</p> : null}
        </div>
      ) : (
        <button type="button" className={`mt-1 flex w-full items-center justify-between gap-2 truncate text-left font-medium ${config ? "hover:text-primary" : ""}`} onClick={() => config && setEditing(true)}>
          <span className="truncate">{renderValue(fieldKey, value)}</span>
          {config ? <Edit3 className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100" /> : null}
        </button>
      )}
    </div>
  );
}

function FullDetails({ kind, record, onSave }: { kind: DetailKind; record: DetailRecord; onSave: (key: string, value: string | number | boolean | null) => Promise<unknown> }) {
  const entries = Object.entries(record).filter(([key]) => !readOnlyKeys.has(key) && !key.endsWith("Id"));
  return (
    <Card>
      <CardHeader><CardTitle>Full Details</CardTitle></CardHeader>
      <CardContent className="grid gap-2 md:grid-cols-2">
        {entries.map(([key, value]) => (
          <InlineField key={key} config={detailInlineEditConfig[kind]?.[key]} fieldKey={key} value={value} onSave={onSave} saving={false} />
        ))}
      </CardContent>
    </Card>
  );
}

function CustomFields({ fields, onSave }: { fields: CustomFieldDetail[]; onSave: (field: CustomFieldDetail, value: string | number | boolean | null) => Promise<unknown> }) {
  return (
    <Card>
      <CardHeader><CardTitle>Custom Fields</CardTitle></CardHeader>
      <CardContent className="grid gap-2 md:grid-cols-2">
        {fields.map((field) => (
          <InlineField
            key={String(field.id)}
            config={customFieldConfig(field)}
            fieldKey={valueText(field.label || field.field_key)}
            value={field.value}
            onSave={(_, value) => onSave(field, value)}
            saving={false}
          />
        ))}
        {!fields.length ? <p className="text-sm text-muted-foreground">No custom fields configured for this record.</p> : null}
      </CardContent>
    </Card>
  );
}

function ApprovalTimeline({ approval }: { approval?: CRMApprovalRequest | null }) {
  const steps = Array.isArray(approval?.steps) ? approval.steps : [];
  return (
    <Card>
      <CardHeader><CardTitle>Approval Timeline</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {approval ? (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <p className="font-medium">{approval.workflow?.name || "Approval request"}</p>
                <p className="text-sm text-muted-foreground">Submitted {formatDate(approval.submittedAt || "")}</p>
              </div>
              <Badge className={statusColor(approval.status)}>{labelFor(approval.status)}</Badge>
            </div>
            {steps.map((step, index) => (
              <div key={String(step.id || index)} className="grid gap-2 rounded-md border bg-muted/20 p-3 md:grid-cols-[1fr_8rem_10rem] md:items-center">
                <p className="text-sm font-medium">Step {index + 1} / Approver {valueText(step.approverId || step.approver_id) || "-"}</p>
                <Badge className={statusColor(valueText(step.status))}>{labelFor(valueText(step.status))}</Badge>
                <p className="text-xs text-muted-foreground">{formatDate(valueText(step.actedAt || step.acted_at))}</p>
              </div>
            ))}
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No approval request has been submitted for this record.</p>
        )}
      </CardContent>
    </Card>
  );
}

function CommunicationTimeline({ recordType, recordId }: { recordType: string; recordId: number }) {
  const [events, setEvents] = useState<CRMApiRecord[]>([]);
  useEffect(() => {
    communicationApi.timeline(recordType, recordId).then((data) => setEvents((data.items || []) as CRMApiRecord[])).catch(() => setEvents([]));
  }, [recordType, recordId]);
  return (
    <Card>
      <CardHeader><CardTitle>Communication Timeline</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {!events.length ? <p className="text-sm text-muted-foreground">No communication events logged yet.</p> : null}
        {events.map((event) => (
          <div key={String(event.id)} className="rounded-md border p-3 text-sm">
            <div className="flex items-center justify-between gap-2"><span className="font-medium">{valueText(event.subject || event.event_type)}</span><Badge variant="outline">{valueText(event.channel)}</Badge></div>
            <p className="mt-1 text-muted-foreground">{valueText(event.summary)}</p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function DetailInlineEditor({ config, value, onChange, onCommit, onCancel }: { config: DetailInlineConfig; value: string; onChange: (value: string) => void; onCommit: () => void; onCancel: () => void }) {
  const common = {
    value,
    autoFocus: true,
    onChange: (event: ChangeEvent<HTMLInputElement | HTMLSelectElement>) => onChange(event.target.value),
    onKeyDown: (event: KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
      if (event.key === "Enter") onCommit();
      if (event.key === "Escape") onCancel();
    },
    onBlur: onCommit,
  };
  if (config.type === "select") {
    return (
      <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" {...common}>
        {(config.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
      </select>
    );
  }
  const type = config.type === "number" ? "number" : config.type === "date" ? "date" : config.type === "datetime" ? "datetime-local" : "text";
  return <Input type={type} value={inputValueForType(config.type, value)} autoFocus onChange={(event) => onChange(event.target.value)} onKeyDown={common.onKeyDown} onBlur={onCommit} />;
}

function normalizeDetailInlineValue(config: DetailInlineConfig, value: string | number | boolean | null) {
  if (value === null || value === "") return null;
  if (config.type === "number") return Number(value);
  if (config.type === "date") return String(value).slice(0, 10);
  if (config.type === "datetime") {
    const date = new Date(String(value));
    return Number.isNaN(date.getTime()) ? value : date.toISOString();
  }
  return value;
}

function inputValueForType(type: InlineFieldType, value: string) {
  if (type === "date") return value ? value.slice(0, 10) : "";
  if (type === "datetime") return value ? value.slice(0, 16) : "";
  return value;
}

function customFieldEditorType(field: CustomFieldDetail): InlineFieldType {
  const fieldType = String(field.fieldType || field.field_type || "text").toLowerCase();
  if (["number", "currency", "decimal", "integer", "user", "owner"].includes(fieldType)) return "number";
  if (fieldType === "date") return "date";
  if (["datetime", "date_time"].includes(fieldType)) return "datetime";
  if (["select", "dropdown", "multi_select"].includes(fieldType)) return "select";
  return "text";
}

function customFieldConfig(field: CustomFieldDetail): DetailInlineConfig {
  const rawOptions = field.options || field.options_json;
  const options = Array.isArray(rawOptions) ? rawOptions.map(String) : undefined;
  return { type: customFieldEditorType(field), options };
}

function Timeline({ events, onAction }: { events: TimelineEvent[]; onAction: (action: QuickAction) => void }) {
  const [filter, setFilter] = useState("all");
  const types = useMemo(() => ["all", ...Array.from(new Set(events.map((event) => timelineType(event)).filter(Boolean)))], [events]);
  const visibleEvents = filter === "all" ? events : events.filter((event) => timelineType(event) === filter);
  return (
    <Card>
      <CardHeader className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <CardTitle>Activity Timeline</CardTitle>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => onAction("note")}><Plus className="h-4 w-4" />Note</Button>
            <Button size="sm" variant="outline" onClick={() => onAction("task")}><CheckCircle2 className="h-4 w-4" />Task</Button>
            <Button size="sm" variant="outline" onClick={() => onAction("call")}><Phone className="h-4 w-4" />Call</Button>
            <Button size="sm" variant="outline" onClick={() => onAction("meeting")}><CalendarDays className="h-4 w-4" />Meeting</Button>
          </div>
        </div>
        <div className="flex gap-2 overflow-x-auto">
          {types.map((type) => (
            <Button key={type} type="button" size="sm" variant={filter === type ? "default" : "outline"} onClick={() => setFilter(type)}>
              {labelFor(type)}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {visibleEvents.map((event, index) => <TimelineEventItem key={`${event.type}-${index}`} event={event} />)}
        {!visibleEvents.length ? <p className="text-sm text-muted-foreground">No timeline activity yet.</p> : null}
      </CardContent>
    </Card>
  );
}

function TimelineEventItem({ event }: { event: TimelineEvent }) {
  const [expanded, setExpanded] = useState(false);
  const Icon = iconForTimeline(timelineType(event));
  const description = valueText(event.record?.body || event.record?.description || event.record?.notes || event.record?.outcome);
  const creator = valueText(event.record?.createdBy || event.record?.created_by_user_id || event.record?.authorId || event.record?.ownerId);
  const mentions = Array.isArray(event.record?.mentions) ? event.record?.mentions as CRMApiRecord[] : [];
  const long = description.length > 150;
  return (
    <div className="flex gap-3 rounded-md border bg-muted/20 p-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"><Icon className="h-4 w-4" /></span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{event.title || labelFor(timelineType(event))}</p>
            <p className="text-xs text-muted-foreground">{formatDate(event.occurredAt || "")}{creator ? ` / User ${creator}` : ""}</p>
          </div>
          <Badge variant="outline">{labelFor(timelineType(event))}</Badge>
        </div>
        {description ? (
          <div className="mt-2 text-sm text-muted-foreground">
            <p className={expanded || !long ? "" : "line-clamp-3"}>{description}</p>
            {long ? <Button variant="link" className="h-auto p-0 text-xs" onClick={() => setExpanded((value) => !value)}>{expanded ? "Collapse" : "Expand"}</Button> : null}
          </div>
        ) : null}
        {mentions.length ? (
          <div className="mt-2 flex flex-wrap gap-2">
            {mentions.map((mention) => {
              const user = mention.user as CRMApiRecord | undefined;
              return <Badge key={String(mention.id)} variant="outline">@{valueText(user?.email || mention.mentionedUserId)}</Badge>;
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function RelatedRecords({ related }: { related: Record<string, unknown> }) {
  const entries = Object.entries(related);
  return (
    <Card>
      <CardHeader><CardTitle>Related Records</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        {entries.map(([key, value]) => (
          <div key={key} className="rounded-md border p-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold">{labelFor(key)}</p>
              <Badge variant="outline">{Array.isArray(value) ? value.length : value ? 1 : 0}</Badge>
            </div>
            {renderRelatedValue(key, value)}
          </div>
        ))}
        {!entries.length ? <p className="text-sm text-muted-foreground">No related records found.</p> : null}
      </CardContent>
    </Card>
  );
}

function EditRecordModal({ record, title, saving, onClose, onSave }: { record: DetailRecord; title: string; saving: boolean; onClose: () => void; onSave: (data: CRMApiRecord) => Promise<void> }) {
  const editableEntries = Object.entries(record).filter(([key, value]) => !readOnlyKeys.has(key) && typeof value !== "object");
  const [draft, setDraft] = useState<CRMApiRecord>(() => Object.fromEntries(editableEntries) as CRMApiRecord);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="max-h-[90vh] w-full max-w-3xl overflow-hidden">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>{title}</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4 overflow-y-auto">
          <div className="grid gap-3 md:grid-cols-2">
            {editableEntries.map(([key]) => (
              <Field key={key} label={labelFor(key)}>
                <Input value={valueText(draft[key])} onChange={(event) => setDraft((current: CRMApiRecord) => ({ ...current, [key]: event.target.value }))} />
              </Field>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={() => onSave(draft)} disabled={saving}>{saving ? "Saving..." : "Save changes"}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

const enrichmentInputFields = [
  ["jobTitle", "Job title"],
  ["company", "Company"],
  ["companyWebsite", "Company website"],
  ["industry", "Industry"],
  ["companySize", "Company size"],
  ["linkedInUrl", "LinkedIn URL"],
  ["location", "Location"],
  ["phone", "Phone"],
  ["emailVerificationStatus", "Email verification"],
] as const;

function EnrichmentModal({ kind, record, recordId, onClose, onDone }: { kind: DetailKind; record: DetailRecord; recordId: number; onClose: () => void; onDone: (record: DetailRecord) => void }) {
  const entityType = kind === "contacts" ? "contact" : "lead";
  const [provider, setProvider] = useState("manual");
  const [draft, setDraft] = useState<CRMApiRecord>(() => ({
    jobTitle: record.job_title || "",
    company: record.company_name || "",
    companyWebsite: record.company_website || record.website || "",
    industry: record.industry || "",
    linkedInUrl: record.linkedin_url || "",
    location: record.city || "",
    phone: record.phone || "",
  }));
  const [preview, setPreview] = useState<CRMEnrichmentPreview | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [history, setHistory] = useState<CRMApiRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    crmApi.enrichmentHistory({ entityType, entityId: recordId }).then((response) => setHistory(response.data.items || [])).catch(() => setHistory([]));
  }, [entityType, recordId]);

  const patch = (key: string, value: CRMApiValue) => setDraft((current) => ({ ...current, [key]: value }));
  const runPreview = () => {
    setLoading(true);
    setError(null);
    crmApi
      .enrichmentPreview({ entityType, entityId: recordId, provider, data: draft })
      .then((response) => {
        setPreview(response.data);
        setSelected(Object.fromEntries((response.data.fields || []).filter((field) => field.supported && field.changed).map((field) => [field.key, true])));
      })
      .catch((err) => setError(err?.response?.data?.detail || "Enrichment preview could not be loaded."))
      .finally(() => setLoading(false));
  };
  const apply = () => {
    if (!preview) return;
    const appliedFields = Object.entries(selected).filter(([, checked]) => checked).map(([key]) => key);
    setLoading(true);
    setError(null);
    crmApi
      .enrichmentApply({ entityType, entityId: recordId, provider, values: preview.values, appliedFields })
      .then((response) => onDone(response.data.record as DetailRecord))
      .catch((err) => setError(err?.response?.data?.detail || "Enrichment could not be applied."))
      .finally(() => setLoading(false));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="max-h-[92vh] w-full max-w-5xl overflow-hidden">
        <CardHeader className="flex-row items-center justify-between">
          <div><CardTitle>Enrich Contact</CardTitle><p className="text-sm text-muted-foreground">Preview provider data and choose exactly which fields to update.</p></div>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4 overflow-y-auto">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-[14rem_1fr]">
            <Field label="Provider">
              <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={provider} onChange={(event) => setProvider(event.target.value)}>
                <option value="manual">Manual enrichment</option>
                <option value="csv_import">CSV/import enrichment</option>
                <option value="third_party">Future third-party provider</option>
              </select>
            </Field>
            <div className="grid gap-3 md:grid-cols-3">
              {enrichmentInputFields.map(([key, label]) => (
                <Field key={key} label={label}>
                  <Input value={valueText(draft[key])} onChange={(event) => patch(key, event.target.value)} />
                </Field>
              ))}
            </div>
          </div>
          <div className="flex justify-between gap-2">
            <div className="text-sm text-muted-foreground">{history.length ? `${history.length} previous enrichment event(s)` : "No enrichment history yet."}</div>
            <Button onClick={runPreview} disabled={loading}><Sparkles className="h-4 w-4" />{loading ? "Checking..." : "Preview enrichment"}</Button>
          </div>
          {preview ? (
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full min-w-[760px] text-sm">
                <thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground">
                  <tr><th className="px-3 py-2">Apply</th><th className="px-3 py-2">Field</th><th className="px-3 py-2">Current</th><th className="px-3 py-2">Enriched</th><th className="px-3 py-2">Status</th></tr>
                </thead>
                <tbody>
                  {preview.fields.map((field) => (
                    <tr key={field.key} className="border-t">
                      <td className="px-3 py-2"><input type="checkbox" disabled={!field.supported || !field.changed} checked={Boolean(selected[field.key])} onChange={(event) => setSelected((current) => ({ ...current, [field.key]: event.target.checked }))} /></td>
                      <td className="px-3 py-2 font-medium">{field.label}</td>
                      <td className="px-3 py-2">{valueText(field.oldValue) || "-"}</td>
                      <td className="px-3 py-2">{valueText(field.newValue) || "-"}</td>
                      <td className="px-3 py-2"><Badge variant={field.supported ? "outline" : "secondary"}>{field.supported ? field.changed ? "Ready" : "No change" : "Preview only"}</Badge></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={apply} disabled={loading || !preview || !Object.values(selected).some(Boolean)}>Apply selected fields</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function QuickActionModal({ action, kind, record, entity, recordId, onClose, onDone }: { action: QuickAction; kind: DetailKind; record: DetailRecord; entity: string; recordId: number; onClose: () => void; onDone: () => void }) {
  const [draft, setDraft] = useState<CRMApiRecord>(() => defaultActionPayload(action, kind, record, entity, recordId));
  const [mentions, setMentions] = useState<MentionUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const targetEntity = actionEntity(action);
  const submit = () => {
    setSaving(true);
    setError(null);
    crmApi
      .create(targetEntity, { ...draft, mentions: mentions.map((user) => ({ id: user.id })) })
      .then(onDone)
      .catch((err) => setError(err?.response?.data?.detail || "Action could not be saved."))
      .finally(() => setSaving(false));
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="w-full max-w-xl">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>{quickActionTitle(action)}</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(draft).filter(([key]) => !key.endsWith("_id")).map(([key, value]) => (
              <Field key={key} label={labelFor(key)}>
                {action === "note" && key === "body" ? (
                  <MentionTextarea
                    value={valueText(value)}
                    onChange={(nextValue) => setDraft((current: CRMApiRecord) => ({ ...current, [key]: nextValue }))}
                    mentions={mentions}
                    onMentionsChange={setMentions}
                  />
                ) : (
                  <Input value={valueText(value)} onChange={(event) => setDraft((current: CRMApiRecord) => ({ ...current, [key]: event.target.value }))} />
                )}
              </Field>
            ))}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={submit} disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MentionTextarea({ value, onChange, mentions, onMentionsChange }: { value: string; onChange: (value: string) => void; mentions: MentionUser[]; onMentionsChange: (users: MentionUser[]) => void }) {
  const [query, setQuery] = useState("");
  const [options, setOptions] = useState<MentionUser[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const handle = window.setTimeout(() => {
      crmApi.searchUsers({ q: query, limit: 8 }).then((response) => setOptions((response.data.items || []) as MentionUser[])).catch(() => setOptions([]));
    }, 180);
    return () => window.clearTimeout(handle);
  }, [query, open]);

  const updateValue = (nextValue: string) => {
    onChange(nextValue);
    const match = nextValue.match(/(?:^|\s)@([A-Za-z0-9._ -]{0,60})$/);
    setQuery(match ? match[1].trim() : "");
    setOpen(Boolean(match));
  };

  const selectUser = (user: MentionUser) => {
    const label = valueText(user.displayName || user.email || `User ${user.id}`);
    const token = `@[${label}](user:${user.id})`;
    const nextValue = value.replace(/(?:^|\s)@([A-Za-z0-9._ -]{0,60})$/, (match) => `${match.startsWith(" ") ? " " : ""}${token} `);
    onChange(nextValue || `${value} ${token} `);
    if (!mentions.some((item) => Number(item.id) === Number(user.id))) {
      onMentionsChange([...mentions, user]);
    }
    setOpen(false);
    setOptions([]);
    setQuery("");
  };

  return (
    <div className="relative md:col-span-2">
      <textarea value={value} onChange={(event) => updateValue(event.target.value)} rows={5} className="w-full rounded-md border bg-background px-3 py-2 text-sm" />
      {open && options.length ? (
        <div className="absolute z-20 mt-1 max-h-56 w-full overflow-y-auto rounded-md border bg-popover p-1 shadow-lg">
          {options.map((user) => (
            <button key={String(user.id)} type="button" className="flex w-full items-center justify-between rounded px-3 py-2 text-left text-sm hover:bg-muted" onClick={() => selectUser(user)}>
              <span className="font-medium">{valueText(user.displayName || user.email)}</span>
              <span className="text-xs text-muted-foreground">{valueText(user.email)}</span>
            </button>
          ))}
        </div>
      ) : null}
      {mentions.length ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {mentions.map((user) => <Badge key={String(user.id)} variant="outline">@{valueText(user.displayName || user.email)}</Badge>)}
        </div>
      ) : <p className="mt-1 text-xs text-muted-foreground">Type @ to mention a teammate.</p>}
    </div>
  );
}

function EmailComposeModal({ kind, record, disabled = false, approvalStatus = "", onClose, onDone }: { kind: DetailKind; record: DetailRecord; disabled?: boolean; approvalStatus?: string; onClose: () => void; onDone: () => void }) {
  const entityType = kind === "accounts" ? "account" : kind.replace(/s$/, "");
  const recordName = titleFor(record, detailConfig[kind].nameKeys, detailConfig[kind].singular);
  const [templates, setTemplates] = useState<CRMApiRecord[]>([]);
  const [attachments, setAttachments] = useState<string[]>([]);
  const [draft, setDraft] = useState<CRMApiRecord>(() => ({
    entityType,
    entityId: Number(record.id),
    to: valueText(record.email),
    cc: "",
    bcc: "",
    subject: `Following up on ${recordName}`,
    body: `<p>Hello,</p><p>Following up on ${recordName}.</p>`,
    saveAsDraft: false,
  }));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    communicationApi.templates().then((response) => setTemplates((response.items || []) as CRMApiRecord[])).catch(() => setTemplates([]));
  }, [entityType]);

  const patch = (key: string, value: CRMApiValue) => setDraft((current: CRMApiRecord) => ({ ...current, [key]: value }));
  const insertToken = (token: string) => patch("body", `${valueText(draft.body)} ${token}`);
  const applyTemplate = (templateId: string) => {
    const template = templates.find((item) => String(item.id) === templateId);
    if (!template) return;
    patch("subject", renderTemplate(valueText(template.subject), record, recordName));
    patch("body", renderTemplate(valueText(template.body_html || template.body_text), record, recordName));
  };
  const submit = (saveAsDraft: boolean) => {
    if (disabled && !saveAsDraft) {
      setError(`Final send is blocked while approval is ${approvalStatus}.`);
      return;
    }
    setSaving(true);
    setError(null);
    const payload = {
      related_record_type: entityType,
      related_record_id: Number(record.id),
      to_email: valueText(draft.to),
      cc: valueText(draft.cc) || undefined,
      bcc: valueText(draft.bcc) || undefined,
      subject: valueText(draft.subject),
      body: valueText(draft.body),
    };
    (saveAsDraft ? communicationApi.draftEmail(payload) : communicationApi.sendEmail(payload))
      .then((response) => {
        const status = String(response.status || "");
        if (status === "failed" || status === "blocked") {
          setError(String(response.error_message || "Email could not be delivered."));
          return;
        }
        onDone();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Email could not be saved."))
      .finally(() => setSaving(false));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="max-h-[92vh] w-full max-w-3xl overflow-hidden">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Send Email</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4 overflow-y-auto">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          {disabled ? <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">Final send is disabled while approval is {approvalStatus}.</div> : null}
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Template">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" onChange={(event) => applyTemplate(event.target.value)} defaultValue="">
                <option value="">Select template</option>
                {templates.map((template) => <option key={String(template.id)} value={String(template.id)}>{valueText(template.name)}</option>)}
              </select>
            </Field>
            <Field label="Insert CRM Field">
              <div className="flex flex-wrap gap-2">
                {["{{contact.name}}", "{{lead.name}}", "{{account.name}}", "{{deal.name}}", "{{record.name}}"].map((token) => (
                  <Button key={token} type="button" size="sm" variant="outline" onClick={() => insertToken(token)}>{token}</Button>
                ))}
              </div>
            </Field>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="To"><Input value={valueText(draft.to)} onChange={(event) => patch("to", event.target.value)} /></Field>
            <Field label="CC"><Input value={valueText(draft.cc)} onChange={(event) => patch("cc", event.target.value)} /></Field>
            <Field label="BCC"><Input value={valueText(draft.bcc)} onChange={(event) => patch("bcc", event.target.value)} /></Field>
            <Field label="Subject"><Input value={valueText(draft.subject)} onChange={(event) => patch("subject", event.target.value)} /></Field>
          </div>
          <Field label="Rich text body">
            <textarea
              value={valueText(draft.body)}
              onChange={(event) => patch("body", event.target.value)}
              rows={10}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            />
          </Field>
          <Field label="Attachments">
            <Input type="file" multiple onChange={(event) => setAttachments(Array.from(event.target.files || []).map((file) => file.name))} />
            {attachments.length ? <p className="text-xs text-muted-foreground">{attachments.join(", ")} will be logged with the draft UI. File upload is not connected for CRM email yet.</p> : null}
          </Field>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button variant="outline" onClick={() => submit(true)} disabled={saving}>Save as draft</Button>
            <Button onClick={() => submit(false)} disabled={saving || disabled}>{saving ? "Sending..." : "Send"}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MessageComposeModal({ kind, record, onClose, onDone }: { kind: DetailKind; record: DetailRecord; onClose: () => void; onDone: () => void }) {
  const entityType = kind === "accounts" ? "account" : kind.replace(/s$/, "");
  const recordName = titleFor(record, detailConfig[kind].nameKeys, detailConfig[kind].singular);
  const [templates, setTemplates] = useState<CRMApiRecord[]>([]);
  const [history, setHistory] = useState<CRMApiRecord[]>([]);
  const [draft, setDraft] = useState<CRMApiRecord>(() => ({
    entityType,
    entityId: Number(record.id),
    channel: "sms",
    to: valueText(record.phone || record.mobile || record.mobile_phone),
    templateId: "",
    body: `Hi ${recordName}, following up from our CRM conversation.`,
  }));
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const channel = valueText(draft.channel) || "sms";
  const body = valueText(draft.body);

  useEffect(() => {
    crmApi.messageTemplates({ entityType, channel }).then((response) => setTemplates(response.data.items || [])).catch(() => setTemplates([]));
    crmApi.messages({ entityType, entityId: Number(record.id) }).then((response) => setHistory(response.data.items || [])).catch(() => setHistory([]));
  }, [entityType, channel, record.id]);

  const patch = (key: string, value: CRMApiValue) => setDraft((current: CRMApiRecord) => ({ ...current, [key]: value }));
  const applyTemplate = (templateId: string) => {
    const template = templates.find((item) => String(item.id) === templateId);
    patch("templateId", templateId);
    if (template) patch("body", renderTemplate(valueText(template.body), record, recordName));
  };
  const submit = () => {
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    const templateId = valueText(draft.templateId);
    crmApi
      .sendMessage({ ...draft, templateId: /^\d+$/.test(templateId) ? Number(templateId) : undefined })
      .then((response) => {
        const status = valueText(response.data.status);
        if (status === "failed") {
          setError(valueText(response.data.failureReason || response.data.failure_reason) || "Message failed to send.");
          return;
        }
        setStatusMessage(`${labelFor(channel)} message ${status || "sent"}.`);
        onDone();
      })
      .catch((err) => setError(err?.response?.data?.detail || "Message could not be sent."))
      .finally(() => setSaving(false));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <Card className="max-h-[92vh] w-full max-w-2xl overflow-hidden">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Send SMS/WhatsApp</CardTitle>
          <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
        </CardHeader>
        <CardContent className="space-y-4 overflow-y-auto">
          {error ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div> : null}
          {statusMessage ? <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{statusMessage}</div> : null}
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Channel">
              <select className="h-10 rounded-md border bg-background px-3 text-sm" value={channel} onChange={(event) => { patch("channel", event.target.value); patch("templateId", ""); }}>
                <option value="sms">SMS</option>
                <option value="whatsapp">WhatsApp</option>
              </select>
            </Field>
            <Field label="To">
              <Input value={valueText(draft.to)} onChange={(event) => patch("to", event.target.value)} placeholder="+919876543210" />
            </Field>
          </div>
          <Field label="Template">
            <select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={valueText(draft.templateId)} onChange={(event) => applyTemplate(event.target.value)}>
              <option value="">Select template</option>
              {templates.map((template) => <option key={String(template.id)} value={String(template.id)}>{valueText(template.name)}</option>)}
            </select>
          </Field>
          <Field label="Message">
            <textarea value={body} onChange={(event) => patch("body", event.target.value)} rows={7} className="w-full rounded-md border bg-background px-3 py-2 text-sm" />
            <div className="mt-1 flex justify-between text-xs text-muted-foreground">
              <span>{channel === "sms" ? `${body.length} characters / ${Math.max(1, Math.ceil(body.length / 160))} SMS segment(s)` : `${body.length} characters`}</span>
              <span>{labelFor(channel)}</span>
            </div>
          </Field>
          {history.length ? (
            <div className="rounded-md border bg-muted/25 p-3">
              <p className="text-sm font-medium">Recent messages</p>
              <div className="mt-2 space-y-2">
                {history.slice(0, 3).map((item) => (
                  <div key={String(item.id)} className="flex items-start justify-between gap-3 text-sm">
                    <span className="line-clamp-1">{valueText(item.body)}</span>
                    <Badge variant="outline">{valueText(item.status)}</Badge>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>Cancel</Button>
            <Button onClick={submit} disabled={saving}>{saving ? "Sending..." : "Send"}</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return <div className="space-y-2"><Label>{label}</Label>{children}</div>;
}

function defaultActionPayload(action: QuickAction, kind: DetailKind, record: DetailRecord, entity: string, recordId: number): CRMApiRecord {
  const linkField = entity === "companies" ? "company_id" : `${entity.replace(/s$/, "")}_id`;
  const linked = { [linkField]: recordId };
  if (action === "note") return { body: `Note for ${titleFor(record, detailConfig[kind].nameKeys, detailConfig[kind].singular)}`, ...linked };
  if (action === "task") return { title: "Follow up", status: "To Do", priority: "Medium", due_date: new Date().toISOString(), ...linked };
  if (action === "call") return { direction: "Outbound", phone_number: valueText(record.phone) || "+91 ", call_time: new Date().toISOString(), outcome: "Logged", ...linked };
  if (action === "email") return { subject: "Follow up", to_email: valueText(record.email) || "customer@example.com", direction: "Outbound", body: "", ...linked };
  if (action === "meeting") return { title: "Customer meeting", start_time: new Date().toISOString(), end_time: new Date(Date.now() + 30 * 60000).toISOString(), status: "Scheduled", location: "", ...linked };
  const today = new Date();
  const expiry = new Date(today.getTime() + 14 * 86400000);
  if (action === "quotation" && kind === "leads") {
    return {
      quote_number: `QT-${Date.now()}`,
      issue_date: today.toISOString().slice(0, 10),
      expiry_date: expiry.toISOString().slice(0, 10),
      status: "Draft",
      total_amount: Number(record.estimated_value || 0),
    };
  }
  return {
    quote_number: `QT-${Date.now()}`,
    issue_date: today.toISOString().slice(0, 10),
    expiry_date: expiry.toISOString().slice(0, 10),
    status: "Draft",
    total_amount: Number(record.amount || record.total_amount || 0),
    ...(kind === "deals" ? { deal_id: recordId, company_id: record.company_id, contact_id: record.contact_id } : linked),
  };
}

function actionEntity(action: QuickAction) {
  if (action === "note") return "notes";
  if (action === "task") return "tasks";
  if (action === "call") return "calls";
  if (action === "email") return "emails";
  if (action === "meeting") return "meetings";
  return "quotations";
}

function quickActionTitle(action: QuickAction) {
  return ({ note: "Add Note", task: "Add Task", call: "Add Call", email: "Send Email", meeting: "Log Meeting", quotation: "Create Quotation" } as Record<QuickAction, string>)[action];
}

function renderRelatedValue(key: string, value: unknown) {
  if (Array.isArray(value)) {
    return value.length ? (
      <div className="space-y-2">
        {value.slice(0, 5).map((item, index) => <RelatedLine key={index} item={item as CRMApiRecord} />)}
      </div>
    ) : <p className="text-sm text-muted-foreground">None</p>;
  }
  if (value && typeof value === "object") return <RelatedLine item={value as CRMApiRecord} />;
  return <p className="text-sm text-muted-foreground">{key === "approval" ? "No approval status" : "None"}</p>;
}

function RelatedLine({ item }: { item: CRMApiRecord }) {
  const label = titleFor(item, ["name", "full_name", "quote_number", "subject", "title", "body"], "Record");
  const status = valueText(item.status || item.lifecycle_stage || item.account_type);
  return (
    <div className="min-w-0 rounded-md bg-muted/35 px-3 py-2 text-sm">
      <p className="truncate font-medium">{label}</p>
      {status ? <p className="text-xs text-muted-foreground">{status}</p> : null}
    </div>
  );
}

function titleFor(record: CRMApiRecord | null | undefined, keys: string[], fallback: string) {
  if (!record) return fallback;
  for (const key of keys) {
    const value = valueText(record[key]);
    if (value) return value;
  }
  return fallback;
}

function approvalFor(record: DetailRecord | null | undefined): CRMApprovalRequest | null {
  const approval = record?.related?.approval;
  if (approval && typeof approval === "object" && valueText((approval as CRMApiRecord).status) !== "not_submitted") return approval as CRMApprovalRequest;
  const approvals = record?.related?.approvals;
  if (Array.isArray(approvals) && approvals.length) return approvals[0] as CRMApprovalRequest;
  return null;
}

function duplicateCountFor(record: DetailRecord | null | undefined) {
  const duplicates = record?.related?.duplicates;
  if (!duplicates || typeof duplicates !== "object") return 0;
  return Number((duplicates as CRMApiRecord).count || 0);
}

function getAiContext(kind: DetailKind) {
  if (kind === "leads") {
    return {
      entityType: "lead",
      agentCode: "crm_lead_qualification",
      prompt: "Analyze this lead and suggest next action.",
    };
  }
  if (kind === "deals") {
    return {
      entityType: "deal",
      agentCode: "crm_deal_analyzer",
      prompt: "Analyze this deal health, risk, and next best action.",
    };
  }
  if (kind === "accounts" || kind === "contacts") {
    return {
      entityType: kind === "accounts" ? "customer" : "contact",
      agentCode: "crm_customer_summary",
      prompt: "Summarize this customer and show key risks/opportunities.",
    };
  }
  return {
    entityType: "quotation",
    agentCode: "crm_deal_analyzer",
    prompt: "Analyze this quotation context and suggest next action.",
  };
}

function renderTemplate(template: string, record: CRMApiRecord, recordName: string) {
  const values: Record<string, string> = {
    "{{record.name}}": recordName,
    "{{lead.name}}": recordName,
    "{{contact.name}}": recordName,
    "{{account.name}}": valueText(record.name || record.company_name) || recordName,
    "{{deal.name}}": valueText(record.name) || recordName,
  };
  return Object.entries(values).reduce((text, [token, value]) => text.split(token).join(value), template);
}

function timelineType(event: TimelineEvent) {
  const recordType = valueText(event.record?.activityType || event.record?.activity_type);
  if (recordType) return recordType;
  const type = valueText(event.type);
  if (type === "notes") return "note";
  if (type === "calls") return "call";
  if (type === "emails") return "email";
  if (type === "tasks") return "task";
  if (type === "meetings") return "meeting";
  if (type === "activities") return "activity";
  return type || "system";
}

function iconForTimeline(type: string) {
  if (type.includes("note")) return FileText;
  if (type.includes("call")) return Phone;
  if (type.includes("message") || type.includes("sms") || type.includes("whatsapp")) return MessageSquare;
  if (type.includes("email")) return Mail;
  if (type.includes("task")) return CheckCircle2;
  if (type.includes("meeting")) return CalendarDays;
  if (type.includes("stage") || type.includes("status") || type.includes("field") || type.includes("owner")) return Clock;
  if (type.includes("quotation") || type.includes("approval")) return FileText;
  return Activity;
}

function labelFor(key: string) {
  return key.replace(/_/g, " ").replace(/([A-Z])/g, " $1").replace(/\b\w/g, (char) => char.toUpperCase());
}

function valueText(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return "";
  return String(value);
}

function renderValue(key: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (key === "lead_score") return `${Number(value)} / ${leadScoreLabel(Number(value))}`;
  if (key.toLowerCase().includes("amount") || key.toLowerCase().includes("revenue") || key === "total") return formatCurrency(Number(value));
  if (key.toLowerCase().includes("date") || key.toLowerCase().includes("_at")) return formatDate(String(value));
  return String(value);
}

function leadScoreLabel(score: number) {
  if (score <= 30) return "Cold";
  if (score <= 70) return "Warm";
  return "Hot";
}
