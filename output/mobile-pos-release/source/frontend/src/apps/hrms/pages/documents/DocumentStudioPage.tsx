import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import "./document-management.css";
import { ImportWizard } from "@/shared/data-transfer";
import { Building2, Settings2, Layers, Clock, Send } from "lucide-react";
import { SmartCreateSection } from "@/shared/creation/SmartCreateSection";
import { NativeSelect } from "@/components/ui/native-select";
import CompactForm from "@/components/forms/CompactForm";
import OrderedList from "@/components/interaction/OrderedList";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import {
  Suspense,
  lazy,
  cloneElement,
  forwardRef,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactElement,
  type TextareaHTMLAttributes,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Award,
  Download,
  Eye,
  FileText,
  Plus,
  RefreshCw,
  Save,
  Copy,
  Upload,
} from "lucide-react";
import { api } from "@/services/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/use-toast";

type CustomField = {
  key: string;
  label: string;
  type: "text" | "multiline" | "date" | "number";
  required: boolean;
  default: string;
};
type Template = {
  id?: number;
  name: string;
  document_type: string;
  kind: string;
  orientation: string;
  recipient_scope: string;
  title: string;
  body: string;
  custom_fields: CustomField[];
  letterhead_id: number | null;
  is_active: boolean;
  version?: number;
};
type Head = {
  id?: number;
  name: string;
  header_text: string;
  footer_text: string;
  accent_color: string;
  show_company_header: boolean;
  logo_asset_id: number | null;
  background_asset_id: number | null;
  signature_asset_id: number | null;
  signatory_name: string;
  signatory_title: string;
  top_margin_mm: number;
  bottom_margin_mm: number;
  is_active: boolean;
  version?: number;
};
type Issued = {
  id: number;
  reference: string;
  recipient_name: string;
  title: string;
  status: string;
  issue_date: string;
  template_version: number;
  issuer_name?: string;
  template_name?: string;
  issued_at?: string;
  revoke_reason?: string;
};
const PdfPreview = lazy(() => import("@/components/PdfPreview"));
const base = "/documents/studio";
const blankTemplate: Template = {
  name: "",
  document_type: "Letter",
  kind: "letter",
  orientation: "portrait",
  recipient_scope: "both",
  title: "",
  body: "Dear {{recipient.name}},\n\n",
  custom_fields: [],
  letterhead_id: null,
  is_active: true,
};
const blankHead: Head = {
  name: "",
  header_text: "",
  footer_text: "",
  accent_color: "#173b56",
  show_company_header: true,
  logo_asset_id: null,
  background_asset_id: null,
  signature_asset_id: null,
  signatory_name: "",
  signatory_title: "Authorized Signatory",
  top_margin_mm: 44,
  bottom_margin_mm: 25,
  is_active: true,
};
const selectClass =
  "h-10 w-full rounded-md border border-input bg-background px-3 text-sm";
const panelClass = "rounded-xl border bg-card p-5 shadow-sm";
const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>((props, ref) => (
  <textarea
    ref={ref}
    {...props}
    className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
  />
));
Textarea.displayName = "StudioTextarea";
const today = () => new Date().toLocaleDateString("en-CA");
async function errorText(error: unknown) {
  if (error instanceof Error && !(error as { response?: unknown }).response)
    return error.message;
  let detail = (error as { response?: { data?: { detail?: unknown } | Blob } })
    ?.response?.data;
  if (detail instanceof Blob) {
    try {
      detail = JSON.parse(await detail.text());
    } catch {
      return "Unable to generate PDF";
    }
  }
  const value = (detail as { detail?: unknown })?.detail;
  return typeof value === "string"
    ? value
    : Array.isArray(value)
      ? value
          .map((v) => `${v.loc?.slice(-1)?.[0] || "Field"}: ${v.msg}`)
          .join("; ")
      : "Request failed. Please try again.";
}
function Field({
  label,
  children,
}: {
  label: string;
  children: ReactElement<{ id?: string }>;
}) {
  const id = useId();
  return (
    <div className="grid gap-2 text-sm">
      <label htmlFor={id} className="font-medium">
        {label}
      </label>
      {cloneElement(children, { id })}
    </div>
  );
}

export default function DocumentStudioPage({
  settingsOnly = false,
}: {
  settingsOnly?: boolean;
}) {
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(() =>
    settingsOnly
      ? params.get("tab") === "letterheads"
        ? "Letterheads"
        : "Templates"
      : params.get("tab") === "templates"
        ? "Templates"
        : params.get("tab") === "letterheads"
          ? "Letterheads"
          : "Generate",
  );
  const [recipientMode, setRecipientMode] = useState("single");
  const [batchIds, setBatchIds] = useState<number[]>([]);
  const [internalNotes, setInternalNotes] = useState("");
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewWarning, setPreviewWarning] = useState("");
  const [templateSearch, setTemplateSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [headId, setHeadId] = useState("");
  const [kind, setKind] = useState("employee");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [recipientId, setRecipientId] = useState(
    params.get("employee_id") || "",
  );
  const [issueDate, setIssueDate] = useState(today);
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState("");
  const [previewFile, setPreviewFile] = useState<Blob | null>(null);
  const [previewKey, setPreviewKey] = useState("");
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [editTemplate, setEditTemplate] = useState<Template | null>(null);
  const [editHead, setEditHead] = useState<Head | null>(null);
  const [issuedPreview, setIssuedPreview] = useState<{
    title: string;
    file: Blob;
  } | null>(null);
  const [historyFilters, setHistoryFilters] = useState({
    status: "",
    issue_from: "",
    issue_to: "",
    sort: "issued_at",
  });
  const [historySearch, setHistorySearch] = useState("");
  const [historyPage, setHistoryPage] = useState(0);
  const [revoke, setRevoke] = useState<Issued | null>(null);
  const [reason, setReason] = useState("");
  const bodyRef = useRef<HTMLTextAreaElement>(null);
  const meta = useQuery({
    queryKey: ["studio", "metadata"],
    queryFn: async () => (await api.get(`${base}/metadata`)).data,
  });
  const templates = useQuery<Template[]>({
    queryKey: ["studio", "templates"],
    queryFn: async () => (await api.get(`${base}/templates`)).data,
  });
  const heads = useQuery<Head[]>({
    queryKey: ["studio", "letterheads"],
    queryFn: async () => (await api.get(`${base}/letterheads`)).data,
  });
  const recipients = useQuery<{ id: number; name: string; detail: string }[]>({
    queryKey: [
      "studio",
      "recipients",
      kind,
      debouncedSearch,
      params.get("employee_id"),
    ],
    queryFn: async () =>
      (
        await api.get(`${base}/recipients`, {
          params: {
            kind,
            q: debouncedSearch,
            employee_id:
              !debouncedSearch && kind === "employee"
                ? params.get("employee_id") || undefined
                : undefined,
          },
        })
      ).data,
    enabled: tab === "Generate" && !!meta.data,
  });
  const history = useQuery<{ total: number; items: Issued[] }>({
    queryKey: [
      "studio",
      "issued",
      historySearch,
      historyPage,
      historyFilters,
      params.get("employee_id"),
    ],
    queryFn: async () =>
      (
        await api.get(`${base}/issued`, {
          params: {
            ...Object.fromEntries(
              Object.entries(historyFilters).filter(([, v]) => v),
            ),
            q: historySearch,
            skip: historyPage * 30,
            employee_id: params.get("employee_id") || undefined,
          },
        })
      ).data,
    enabled: tab === "Issued",
  });
  const recent = useQuery<{ total: number; items: Issued[] }>({
    queryKey: ["studio", "recent", params.get("employee_id")],
    enabled: tab === "Generate",
    queryFn: async () =>
      (
        await api.get(`${base}/issued`, {
          params: {
            limit: 5,
            employee_id: params.get("employee_id") || undefined,
          },
          recordCache: false,
        })
      ).data,
  });
  const template = templates.data?.find((t) => String(t.id) === templateId);
  const head = heads.data?.find((h) => String(h.id) === headId);
  const payload = {
    template_id: template?.id,
    template_version: template?.version,
    letterhead_id: head?.id,
    letterhead_version: head?.version,
    recipient_type: kind,
    recipient_id: Number(recipientId),
    issue_date: issueDate,
    variables,
    internal_notes: internalNotes,
    request_key: requestKey,
  };
  const payloadKey = JSON.stringify({ ...payload, request_key: undefined });
  const latestPayload = useRef(payload);
  latestPayload.current = payload;
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    if (preview) return () => URL.revokeObjectURL(preview);
  }, [preview]);
  useEffect(() => {
    setPreview("");
    setPreviewFile(null);
    setPreviewKey("");
    setRequestKey(crypto.randomUUID());
  }, [templateId, headId, kind, recipientId, issueDate, variables]);
  useEffect(() => {
    if (
      tab !== "Generate" ||
      !templateId ||
      !headId ||
      !recipientId ||
      !issueDate
    )
      return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      setPreviewBusy(true);
      setPreviewWarning("");
      void api
        .post(`${base}/preview`, latestPayload.current, {
          responseType: "blob",
          signal: controller.signal,
          progress: false,
        })
        .then((response) => {
          if (controller.signal.aborted) return;
          setPreview(URL.createObjectURL(response.data));
          setPreviewFile(response.data);
          setPreviewKey(payloadKey);
        })
        .catch(async (error) => {
          if (!controller.signal.aborted)
            setPreviewWarning(await errorText(error));
        })
        .finally(() => {
          if (!controller.signal.aborted) setPreviewBusy(false);
        });
    }, 650);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [payloadKey, tab, recipientMode, batchIds]);
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setNotice("");
    try {
      await action();
    } catch (error) {
      const message = await errorText(error);
      setNotice(message);
      toast({
        title: "Action could not be completed",
        description: message,
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  }
  async function refresh() {
    await qc.invalidateQueries({ queryKey: ["studio"] });
  }
  async function download(document: Issued) {
    const response = await api.get(`${base}/issued/${document.id}/pdf`, {
      responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${document.reference}.pdf`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function viewIssued(document: Issued) {
    const response = await api.get(`${base}/issued/${document.id}/pdf`, {
      responseType: "blob",
      recordCache: false,
    });
    setIssuedPreview({ title: document.title, file: response.data });
  }
  async function shareIssued(document: Issued) {
    if (navigator.share && navigator.canShare) {
      const response = await api.get(`${base}/issued/${document.id}/pdf`, {
        responseType: "blob",
        recordCache: false,
      });
      const file = new File([response.data], `${document.reference}.pdf`, {
        type: "application/pdf",
      });
      if (navigator.canShare({ files: [file] })) {
        await navigator.share({ title: document.title, files: [file] });
        return;
      }
    }
    await navigator.clipboard.writeText(document.reference);
    toast({
      title: "Document reference copied",
      description: "Private files remain accessible only to authorized users.",
    });
  }
  function selectTemplate(value: string) {
    setTemplateId(value);
    const item = templates.data?.find((t) => String(t.id) === value);
    setVariables(
      Object.fromEntries(
        (item?.custom_fields || []).map((f) => [f.key, f.default]),
      ),
    );
    if (item?.letterhead_id) setHeadId(String(item.letterhead_id));
    if (item?.recipient_scope !== "both" && item?.recipient_scope !== kind) {
      setKind(item?.recipient_scope || "employee");
      setRecipientId("");
    }
  }
  async function saveTemplate() {
    if (!editTemplate) return;
    const { id, ...data } = editTemplate;
    await api.request({
      method: id ? "put" : "post",
      url: `${base}/templates${id ? `/${id}` : ""}`,
      data,
    });
    setEditTemplate(null);
    await refresh();
    toast({ title: "Template saved" });
  }
  async function saveHead() {
    if (!editHead) return;
    const { id, ...data } = editHead;
    await api.request({
      method: id ? "put" : "post",
      url: `${base}/letterheads${id ? `/${id}` : ""}`,
      data,
    });
    setEditHead(null);
    await refresh();
    toast({ title: "Letterhead saved" });
  }
  function insertPlaceholder(key: string) {
    if (!editTemplate) return;
    const field = bodyRef.current;
    const token = `{{${key}}}`;
    const start = field?.selectionStart ?? editTemplate.body.length;
    const end = field?.selectionEnd ?? start;
    setEditTemplate({
      ...editTemplate,
      body:
        editTemplate.body.slice(0, start) +
        token +
        editTemplate.body.slice(end),
    });
    requestAnimationFrame(() => {
      field?.focus();
      field?.setSelectionRange(start + token.length, start + token.length);
    });
  }
  const failed = meta.isError || templates.isError || heads.isError;
  if (!settingsOnly && params.get("tab") === "letterheads")
    return <Navigate replace to={`/settings/documents?${params.toString()}`} />;
  return (
    <div className="document-management studio-workspace space-y-5">
      <div className="dm-hero">
        <span className="dm-hero-icon">
          <FileText size={30} />
        </span>
        <div>
          <p className="dm-eyebrow">DOCUMENTS / LETTERS & CERTIFICATES</p>
          <h1 className="flex items-center gap-2 text-2xl font-semibold">
            <FileText className="h-6 w-6" />
            Letters & Certificates Studio
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Create documents from live records, reusable templates and your
            company letterheads.
          </p>
        </div>
        <Button
          variant="outline"
          disabled={busy}
          onClick={() => void run(refresh)}
        >
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>
      {notice && (
        <div
          role="alert"
          className="rounded-lg border border-destructive p-3 text-sm text-destructive"
        >
          {notice}
        </div>
      )}
      {failed ? (
        <div role="alert" className={panelClass}>
          Unable to load Document Studio. Check your access and retry using
          Refresh.
        </div>
      ) : meta.isPending ? (
        <p role="status">Loading Document Studio…</p>
      ) : (
        <>
          <div
            className="dm-tabs"
            role="tablist"
            aria-label="Document studio sections"
          >
            {[
              ...(!settingsOnly ? ["Generate"] : []),
              ...(meta.data?.can_edit_templates
                ? settingsOnly
                  ? ["Templates", "Letterheads"]
                  : ["Templates"]
                : []),
              ...(!settingsOnly ? ["Issued"] : []),
            ].map((name) => (
              <Button
                key={name}
                role="tab"
                aria-selected={tab === name}
                aria-current={tab === name ? "page" : undefined}
                variant={tab === name ? "default" : "outline"}
                onClick={() => setTab(name)}
              >
                {name === "Issued" ? "Issued History" : name}
              </Button>
            ))}
          </div>
          {!templates.isPending && !templates.data?.length && (
            <div className={panelClass}>
              <h2 className="font-semibold">Set up your document studio</h2>
              <p className="my-2 text-sm text-muted-foreground">
                Add 12 editable letter and certificate templates and a
                letterhead using your company profile. Review the wording and
                upload your official artwork before issuing documents.
              </p>
              {meta.data?.can_edit_templates && (
                <Button
                  disabled={busy}
                  onClick={() =>
                    void run(async () => {
                      await api.post(`${base}/initialize?extended=true`);
                      await refresh();
                    })
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add starter templates
                </Button>
              )}
            </div>
          )}
          {tab === "Generate" && (
            <div className="studio-generation">
              <section className={panelClass}>
                <h2 className="mb-4 font-semibold">
                  Generate Letter / Certificate
                </h2>
                <CompactForm
                  compactTabs={false}
                  className="space-y-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void run(async () => {
                      const response = await api.post(
                        `${base}/preview`,
                        payload,
                        { responseType: "blob" },
                      );
                      setPreview(URL.createObjectURL(response.data));
                      setPreviewFile(response.data);
                      setPreviewKey(payloadKey);
                    });
                  }}
                >
                  <Field label="Template">
                    <NativeSelect
                      loading={templates.isFetching}
                      error={templates.isError}
                      aria-label="Template"
                      className={selectClass}
                      required
                      value={templateId}
                      onChange={(e) => selectTemplate(e.target.value)}
                    >
                      <option value="">Choose a template</option>
                      {templates.data
                        ?.filter((t) => t.is_active)
                        .map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name} · v{t.version}
                          </option>
                        ))}
                    </NativeSelect>
                  </Field>
                  <Field label="Letterhead">
                    <NativeSelect
                      loading={heads.isFetching}
                      error={heads.isError}
                      aria-label="Letterhead"
                      className={selectClass}
                      required
                      value={headId}
                      onChange={(e) => setHeadId(e.target.value)}
                    >
                      <option value="">Choose a letterhead</option>
                      {heads.data
                        ?.filter((h) => h.is_active)
                        .map((h) => (
                          <option key={h.id} value={h.id}>
                            {h.name} · v{h.version}
                          </option>
                        ))}
                    </NativeSelect>
                  </Field>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Recipient source">
                      <NativeSelect
                        loading={meta.isFetching}
                        error={meta.isError}
                        aria-label="Recipient source"
                        className={selectClass}
                        value={kind}
                        onChange={(e) => {
                          setKind(e.target.value);
                          setRecipientId("");
                        }}
                      >
                        <option
                          value="employee"
                          disabled={template?.recipient_scope === "application"}
                        >
                          Employee / onboarded intern
                        </option>
                        {meta.data?.can_use_applications && (
                          <option
                            value="application"
                            disabled={template?.recipient_scope === "employee"}
                          >
                            Internship applicant
                          </option>
                        )}
                      </NativeSelect>
                    </Field>
                    <Field label="Issue date">
                      <Input
                        aria-label="Issue date"
                        type="date"
                        required
                        value={issueDate}
                        onChange={(e) => setIssueDate(e.target.value)}
                      />
                    </Field>
                  </div>
                  <div className="grid gap-2">
                    <Label>Recipient selection</Label>
                    <div className="flex flex-wrap gap-2">
                      {[
                        ["single", "Single recipient"],
                        ["multiple", "Multiple employees"],
                        ["custom", "Custom list"],
                      ].map(([value, label]) => (
                        <Button
                          key={value}
                          type="button"
                          size="sm"
                          variant={
                            recipientMode === value ? "default" : "outline"
                          }
                          onClick={() => {
                            setRecipientMode(value);
                            setBatchIds([]);
                          }}
                        >
                          {label}
                        </Button>
                      ))}
                    </div>
                  </div>
                  {recipientMode === "custom" && (
                    <ImportWizard
                      title="Import recipient list"
                      label="Map CSV / Excel recipients"
                      description="Map employee record IDs. Names and sensitive fields are read from authorized HRMS records, not the spreadsheet."
                      maxRows={50}
                      fields={[
                        {
                          key: "recipient_id",
                          label: "Employee record ID",
                          type: "number",
                          required: true,
                        },
                      ]}
                      onImport={async ({ rows }) => {
                        const ids = [
                          ...new Set(rows.map((r) => Number(r.recipient_id))),
                        ];
                        if (ids.some((id) => !Number.isInteger(id) || id <= 0))
                          throw new Error("Use valid employee record IDs");
                        setBatchIds(ids);
                        setKind("employee");
                        setRecipientId(String(ids[0] || ""));
                        return {
                          message: `${ids.length} recipients selected. Every employee is validated before issuance.`,
                        };
                      }}
                    />
                  )}
                  {recipientMode !== "single" && (
                    <div className="studio-batch-list">
                      <p className="text-xs">
                        {batchIds.length} recipients selected · maximum 50
                      </p>
                      {recipientMode === "multiple" &&
                        recipients.data?.map((r) => (
                          <label key={r.id}>
                            <input
                              type="checkbox"
                              checked={batchIds.includes(r.id)}
                              onChange={(e) => {
                                const next = e.target.checked
                                  ? [...batchIds, r.id]
                                  : batchIds.filter((id) => id !== r.id);
                                if (next.length > 50) return;
                                setBatchIds(next);
                                setRecipientId(String(next[0] || ""));
                              }}
                            />
                            {r.name} · {r.detail}
                          </label>
                        ))}
                    </div>
                  )}
                  <Field label="Find recipient">
                    <Input
                      placeholder="Search name or reference…"
                      value={search}
                      onChange={(e) => {
                        setSearch(e.target.value);
                        setRecipientId("");
                      }}
                    />
                  </Field>
                  <Field label="Recipient">
                    <NativeSelect
                      loading={recipients.isFetching}
                      error={recipients.isError}
                      aria-label="Recipient"
                      required
                      className={selectClass}
                      value={recipientId}
                      onChange={(e) => setRecipientId(e.target.value)}
                    >
                      <option value="">
                        {recipients.isFetching
                          ? "Loading…"
                          : "Choose a recipient"}
                      </option>
                      {recipients.data?.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} · {r.detail}
                        </option>
                      ))}
                    </NativeSelect>
                  </Field>
                  {recipients.isError && (
                    <p role="alert" className="text-sm text-destructive">
                      Unable to load recipients. Refresh and try again.
                    </p>
                  )}
                  {template?.custom_fields.map((field) => (
                    <Field
                      key={field.key}
                      label={`${field.label}${field.required ? " *" : ""}`}
                    >
                      {field.type === "multiline" ? (
                        <Textarea
                          required={field.required}
                          maxLength={2000}
                          value={variables[field.key] || ""}
                          onChange={(e) =>
                            setVariables({
                              ...variables,
                              [field.key]: e.target.value,
                            })
                          }
                        />
                      ) : (
                        <Input
                          type={field.type === "text" ? "text" : field.type}
                          step={field.type === "number" ? "any" : undefined}
                          required={field.required}
                          maxLength={2000}
                          value={variables[field.key] || ""}
                          onChange={(e) =>
                            setVariables({
                              ...variables,
                              [field.key]: e.target.value,
                            })
                          }
                        />
                      )}
                    </Field>
                  ))}
                  <Field label="Signatory">
                    <Input
                      readOnly
                      value={
                        head?.signatory_name
                          ? `${head.signatory_name} · ${head.signatory_title}`
                          : "Configured in the selected letterhead"
                      }
                    />
                  </Field>
                  <Field label="Internal remarks">
                    <Textarea
                      maxLength={2000}
                      value={internalNotes}
                      onChange={(e) => setInternalNotes(e.target.value)}
                    />
                  </Field>
                  <p className="text-xs text-muted-foreground">
                    Names, employment details and company details come from the
                    database. Custom fields supply approved terms and program
                    details.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      type="submit"
                      disabled={busy || !template || !head || !recipientId}
                    >
                      <Eye className="mr-2 h-4 w-4" />
                      Preview PDF
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy || !preview || previewKey !== payloadKey}
                      onClick={() =>
                        void run(async () => {
                          if (recipientMode !== "single") {
                            if (!batchIds.length)
                              throw new Error("Select at least one recipient");
                            // Validate every recipient before issuing any official record.
                            for (const id of batchIds)
                              await api.post(
                                `${base}/preview`,
                                {
                                  ...payload,
                                  recipient_type: "employee",
                                  recipient_id: id,
                                },
                                { responseType: "blob" },
                              );
                            let issuedCount = 0;
                            try {
                              for (const id of batchIds) {
                                await api.post(`${base}/issue`, {
                                  ...payload,
                                  recipient_type: "employee",
                                  recipient_id: id,
                                  request_key: `${requestKey}-${id}`,
                                });
                                issuedCount++;
                              }
                            } catch (error) {
                              await qc.invalidateQueries({
                                queryKey: ["studio", "issued"],
                              });
                              throw new Error(
                                `${issuedCount} of ${batchIds.length} documents issued. Retry with the same selection to resume without duplicates. ${await errorText(error)}`,
                              );
                            }
                            await qc.invalidateQueries({
                              queryKey: ["studio", "issued"],
                            });
                            setTab("Issued");
                            setNotice(
                              `${batchIds.length} personalized documents issued. Download each from Issued History.`,
                            );
                            return;
                          }
                          const result = (
                            await api.post(`${base}/issue`, payload)
                          ).data as Issued;
                          setRequestKey(crypto.randomUUID());
                          setPreview("");
                          setPreviewFile(null);
                          setPreviewKey("");
                          await qc.invalidateQueries({ queryKey: ["studio"] });
                          toast({
                            title: `Issued ${result.reference}`,
                            description:
                              "The original data and template version have been saved.",
                          });
                          await download(result);
                        })
                      }
                    >
                      <Award className="mr-2 h-4 w-4" />
                      {recipientMode === "single"
                        ? "Issue & download"
                        : `Issue ${batchIds.length} documents`}
                    </Button>
                  </div>
                </CompactForm>
              </section>
              <section className={`${panelClass} studio-preview-panel`}>
                <h2 className="mb-3 font-semibold">Live Preview (PDF)</h2>
                <p className="studio-auto-status">
                  {previewBusy
                    ? "Updating private preview…"
                    : "Preview updates as you prepare. No official record is created."}
                </p>
                {previewWarning && (
                  <p role="alert" className="dm-notice">
                    {previewWarning}
                  </p>
                )}
                {preview && previewKey === payloadKey ? (
                  <>
                    {previewFile && (
                      <Suspense
                        fallback={<p role="status">Loading PDF viewer…</p>}
                      >
                        <PdfPreview file={previewFile} zoomControls />
                      </Suspense>
                    )}
                    <Button asChild variant="outline">
                      <a
                        className="mt-3 inline-block text-sm underline"
                        href={preview}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open preview in a new tab
                      </a>
                    </Button>
                  </>
                ) : (
                  <div className="flex h-96 flex-col items-center justify-center gap-3 text-center text-muted-foreground">
                    <FileText className="h-14 w-14" />
                    <p>
                      Choose a template and recipient, then preview.
                      <br />
                      Previewing does not issue a document.
                    </p>
                  </div>
                )}
              </section>
              <aside className="studio-tools">
                <section>
                  <h2>
                    <Settings2 size={18} className="inline mr-2" />
                    Document Studio Setup
                  </h2>
                  <p className="text-xs text-muted-foreground">
                    Reusable templates, trusted signatures and company branding.
                  </p>
                  {meta.data?.can_edit_templates && (
                    <>
                      <button
                        className="studio-tool-link"
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            await api.post(`${base}/initialize?extended=true`);
                            await refresh();
                            setNotice(
                              "Starter templates added. Existing templates are preserved.",
                            );
                          })
                        }
                      >
                        <Layers size={23} />
                        <span>
                          Starter templates
                          <small>Experience, employment, salary and more</small>
                        </span>
                      </button>
                      <Link
                        className="studio-tool-link"
                        to="/settings/documents?tab=letterheads"
                      >
                        <Building2 size={23} />
                        <span>
                          Letterheads & signatories
                          <small>
                            Logos, signatures, margins and company branding
                          </small>
                        </span>
                      </Link>
                      <button
                        className="studio-tool-link"
                        onClick={() => setTab("Templates")}
                      >
                        <FileText size={23} />
                        <span>
                          Template library
                          <small>
                            Browse, customize and manage active versions
                          </small>
                        </span>
                      </button>
                    </>
                  )}
                </section>
                <section>
                  <div className="flex items-center justify-between gap-2">
                    <h2>
                      <Clock size={17} className="inline mr-2" />
                      Recently Issued
                    </h2>
                    <button
                      className="text-xs text-primary"
                      onClick={() => setTab("Issued")}
                    >
                      View all →
                    </button>
                  </div>
                  {recent.isFetching && (
                    <p role="status" className="studio-empty">
                      Loading issued documents…
                    </p>
                  )}
                  {recent.data?.items.slice(0, 5).map((item) => (
                    <article className="studio-recent-row" key={item.id}>
                      <FileText size={19} />
                      <div>
                        <strong>{item.title}</strong>
                        <p>
                          {item.recipient_name} · {item.issue_date}
                        </p>
                        <span className="dv-tag">{item.status}</span>
                      </div>
                      <button
                        aria-label={`Download ${item.reference}`}
                        disabled={busy}
                        onClick={() => void run(() => download(item))}
                      >
                        <Download size={17} />
                      </button>
                    </article>
                  ))}
                  {!recent.isFetching && !recent.data?.items.length && (
                    <p className="studio-empty">
                      Your issued documents will appear here. Previewing a
                      letter does not issue it.
                    </p>
                  )}
                </section>
              </aside>
            </div>
          )}
          {tab === "Templates" && (
            <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
              <aside className={`${panelClass} space-y-2`}>
                <Button
                  className="w-full"
                  onClick={() =>
                    setEditTemplate(structuredClone(blankTemplate))
                  }
                >
                  <Plus className="mr-2 h-4 w-4" />
                  New template
                </Button>
                <Input
                  aria-label="Search templates"
                  placeholder="Search templates…"
                  value={templateSearch}
                  onChange={(e) => setTemplateSearch(e.target.value)}
                />
                {templates.data
                  ?.filter((t) =>
                    (t.name + " " + t.document_type)
                      .toLowerCase()
                      .includes(templateSearch.toLowerCase()),
                  )
                  .map((t) => (
                    <button
                      key={t.id}
                      className="w-full rounded border p-3 text-left text-sm hover:bg-muted"
                      onClick={() => setEditTemplate(structuredClone(t))}
                    >
                      <strong className="block">{t.name}</strong>
                      <span className="text-xs text-muted-foreground">
                        {t.kind} · v{t.version} ·{" "}
                        {t.is_active ? "Active" : "Archived"}
                      </span>
                    </button>
                  ))}
              </aside>
              <section className={panelClass}>
                {!editTemplate ? (
                  <div className="studio-template-grid">
                    {templates.data
                      ?.filter((t) =>
                        (t.name + " " + t.document_type)
                          .toLowerCase()
                          .includes(templateSearch.toLowerCase()),
                      )
                      .map((t) => (
                        <button
                          className="studio-template-tile"
                          key={t.id}
                          onClick={() => setEditTemplate(structuredClone(t))}
                        >
                          <FileText size={32} className="text-primary" />
                          <h3>{t.name}</h3>
                          <p>
                            {t.document_type} · v{t.version}
                          </p>
                          <span className="dv-tag">
                            {t.is_active ? "Active" : "Archived"}
                          </span>
                        </button>
                      ))}
                  </div>
                ) : (
                  <SmartCreateSection
                    title={
                      editTemplate?.id ? "Edit template" : "Create template"
                    }
                    autoOpen
                    onClose={() => setEditTemplate(null)}
                    size="large"
                  >
                    <CompactForm
                      className="space-y-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void run(saveTemplate);
                      }}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <h2 className="font-semibold">
                          {editTemplate.id ? "Edit template" : "New template"}
                        </h2>
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() =>
                            setEditTemplate({
                              ...editTemplate,
                              id: undefined,
                              version: undefined,
                              name: `${editTemplate.name} copy`.slice(0, 150),
                            })
                          }
                        >
                          <Copy className="mr-2 h-4 w-4" />
                          Duplicate
                        </Button>
                      </div>
                      <Field label="Template name">
                        <Input
                          required
                          maxLength={150}
                          value={editTemplate.name}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              name: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <div className="grid gap-4 sm:grid-cols-3">
                        <Field label="Kind">
                          <NativeSelect
                            className={selectClass}
                            value={editTemplate.kind}
                            onChange={(e) =>
                              setEditTemplate({
                                ...editTemplate,
                                kind: e.target.value,
                              })
                            }
                          >
                            <option value="letter">Letter</option>
                            <option value="certificate">Certificate</option>
                          </NativeSelect>
                        </Field>
                        <Field label="Orientation">
                          <NativeSelect
                            className={selectClass}
                            value={editTemplate.orientation}
                            onChange={(e) =>
                              setEditTemplate({
                                ...editTemplate,
                                orientation: e.target.value,
                              })
                            }
                          >
                            <option value="portrait">Portrait</option>
                            <option value="landscape">Landscape</option>
                          </NativeSelect>
                        </Field>
                        <Field label="Recipients">
                          <NativeSelect
                            className={selectClass}
                            value={editTemplate.recipient_scope}
                            onChange={(e) =>
                              setEditTemplate({
                                ...editTemplate,
                                recipient_scope: e.target.value,
                              })
                            }
                          >
                            <option value="both">Employees & applicants</option>
                            <option value="employee">Employees only</option>
                            <option value="application">Applicants only</option>
                          </NativeSelect>
                        </Field>
                      </div>
                      <Field label="Document category">
                        <Input
                          required
                          maxLength={80}
                          value={editTemplate.document_type}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              document_type: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Default letterhead">
                        <NativeSelect
                          loading={heads.isFetching}
                          error={heads.isError}
                          className={selectClass}
                          value={editTemplate.letterhead_id || ""}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              letterhead_id: Number(e.target.value) || null,
                            })
                          }
                        >
                          <option value="">Choose at generation</option>
                          {heads.data?.map((h) => (
                            <option key={h.id} value={h.id}>
                              {h.name}
                            </option>
                          ))}
                        </NativeSelect>
                      </Field>
                      <Field label="Document title (placeholders supported)">
                        <Input
                          required
                          maxLength={250}
                          value={editTemplate.title}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              title: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Body · plain text and {{group.field}} placeholders">
                        <Textarea
                          ref={bodyRef}
                          required
                          rows={12}
                          maxLength={20000}
                          value={editTemplate.body}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              body: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <details className="rounded border p-3">
                        <summary className="cursor-pointer text-sm font-medium">
                          Insert database placeholder
                        </summary>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {[
                            ...(meta.data?.placeholders || []),
                            ...editTemplate.custom_fields.map(
                              (f) => `custom.${f.key}`,
                            ),
                          ].map((key: string) => (
                            <button
                              type="button"
                              className="rounded border px-2 py-1 font-mono text-xs hover:bg-muted"
                              key={key}
                              onClick={() => insertPlaceholder(key)}
                            >{`{{${key}}}`}</button>
                          ))}
                        </div>
                      </details>
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <Label>Custom placeholders</Label>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={editTemplate.custom_fields.length >= 20}
                            onClick={() =>
                              setEditTemplate({
                                ...editTemplate,
                                custom_fields: [
                                  ...editTemplate.custom_fields,
                                  {
                                    key: `field_${editTemplate.custom_fields.length + 1}`,
                                    label: "New field",
                                    type: "text",
                                    required: true,
                                    default: "",
                                  },
                                ],
                              })
                            }
                          >
                            <Plus className="mr-1 h-4 w-4" />
                            Add field
                          </Button>
                        </div>
                        <OrderedList
                          label="Document field order"
                          items={editTemplate.custom_fields.map((f, index) => ({
                            ...f,
                            id: index,
                          }))}
                          title={(f) => f.label || f.key || "New field"}
                          onReorder={async (ordered) =>
                            setEditTemplate({
                              ...editTemplate,
                              custom_fields: ordered.map(
                                ({ id, ...field }) => field,
                              ),
                            })
                          }
                        />
                        {editTemplate.custom_fields.map((field, index) => {
                          const change = (patch: Partial<CustomField>) =>
                            setEditTemplate({
                              ...editTemplate,
                              custom_fields: editTemplate.custom_fields.map(
                                (f, i) =>
                                  i === index ? { ...f, ...patch } : f,
                              ),
                            });
                          return (
                            <div
                              className="grid gap-3 rounded border p-3 sm:grid-cols-2"
                              key={index}
                            >
                              <Field label="Key · custom.key">
                                <Input
                                  required
                                  pattern="[a-z][a-z0-9_]{0,49}"
                                  value={field.key}
                                  onChange={(e) =>
                                    change({ key: e.target.value })
                                  }
                                />
                              </Field>
                              <Field label="Label">
                                <Input
                                  required
                                  value={field.label}
                                  onChange={(e) =>
                                    change({ label: e.target.value })
                                  }
                                />
                              </Field>
                              <Field label="Input type">
                                <NativeSelect
                                  className={selectClass}
                                  value={field.type}
                                  onChange={(e) =>
                                    change({
                                      type: e.target
                                        .value as CustomField["type"],
                                    })
                                  }
                                >
                                  {["text", "multiline", "date", "number"].map(
                                    (type) => (
                                      <option key={type}>{type}</option>
                                    ),
                                  )}
                                </NativeSelect>
                              </Field>
                              <Field label="Default value">
                                <Input
                                  value={field.default}
                                  onChange={(e) =>
                                    change({ default: e.target.value })
                                  }
                                />
                              </Field>
                              <label className="flex items-center gap-2 text-sm">
                                <input
                                  type="checkbox"
                                  checked={field.required}
                                  onChange={(e) =>
                                    change({ required: e.target.checked })
                                  }
                                />
                                Required
                              </label>
                              <Button
                                type="button"
                                variant="ghost"
                                onClick={() =>
                                  setEditTemplate({
                                    ...editTemplate,
                                    custom_fields:
                                      editTemplate.custom_fields.filter(
                                        (_, i) => i !== index,
                                      ),
                                  })
                                }
                              >
                                Remove field
                              </Button>
                            </div>
                          );
                        })}
                      </div>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={editTemplate.is_active}
                          onChange={(e) =>
                            setEditTemplate({
                              ...editTemplate,
                              is_active: e.target.checked,
                            })
                          }
                        />
                        Active template
                      </label>
                      <p className="text-xs text-muted-foreground">
                        Saving creates a new version. Previously issued
                        documents keep their original wording.
                      </p>
                      <Button disabled={busy}>
                        <Save className="mr-2 h-4 w-4" />
                        Save template
                      </Button>
                    </CompactForm>
                  </SmartCreateSection>
                )}
              </section>
            </div>
          )}
          {tab === "Letterheads" && (
            <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
              <aside className={`${panelClass} space-y-2`}>
                <Button
                  className="w-full"
                  onClick={() => setEditHead(structuredClone(blankHead))}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  New letterhead
                </Button>
                {heads.data?.map((h) => (
                  <button
                    key={h.id}
                    className="w-full rounded border p-3 text-left text-sm hover:bg-muted"
                    onClick={() => setEditHead(structuredClone(h))}
                  >
                    <strong className="block">{h.name}</strong>
                    <span className="text-xs text-muted-foreground">
                      v{h.version} · {h.is_active ? "Active" : "Archived"}
                    </span>
                  </button>
                ))}
              </aside>
              <section className={panelClass}>
                {!editHead ? (
                  <p>
                    Select a letterhead to configure your official branding.
                  </p>
                ) : (
                  <SmartCreateSection
                    title={
                      editHead?.id ? "Edit letterhead" : "Create letterhead"
                    }
                    autoOpen
                    onClose={() => setEditHead(null)}
                    size="large"
                  >
                    <CompactForm
                      className="space-y-4"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void run(saveHead);
                      }}
                    >
                      <h2 className="font-semibold">Letterhead settings</h2>
                      <p className="text-sm text-muted-foreground">
                        Company name, address and contact information come from
                        your company profile. Upload your official letterhead as
                        a PDF, PNG or JPEG, or use a logo with the company
                        header.
                      </p>
                      {meta.data?.has_company_logo && (
                        <Button
                          type="button"
                          variant="outline"
                          disabled={busy}
                          onClick={() =>
                            void run(async () => {
                              const result = await api.post(
                                `${base}/company-logo`,
                              );
                              setEditHead((current) =>
                                current
                                  ? {
                                      ...current,
                                      logo_asset_id: result.data.id,
                                    }
                                  : current,
                              );
                            })
                          }
                        >
                          Use logo from company profile
                        </Button>
                      )}
                      <Field label="Letterhead name">
                        <Input
                          required
                          maxLength={150}
                          value={editHead.name}
                          onChange={(e) =>
                            setEditHead({ ...editHead, name: e.target.value })
                          }
                        />
                      </Field>
                      <div className="grid gap-4 sm:grid-cols-3">
                        {(
                          [
                            ["logo_asset_id", "Logo", "logo"],
                            [
                              "background_asset_id",
                              "Full-page artwork",
                              "background",
                            ],
                            ["signature_asset_id", "Signature", "signature"],
                          ] as const
                        ).map(([key, label, assetKind]) => (
                          <div
                            className="space-y-2 rounded border p-3"
                            key={key}
                          >
                            <Label>{label}</Label>
                            <p className="text-xs text-muted-foreground">
                              {editHead[key]
                                ? `Saved artwork #${editHead[key]}`
                                : "No artwork"}
                            </p>
                            <label className="flex cursor-pointer items-center gap-2 text-sm text-primary">
                              <Upload className="h-4 w-4" />
                              Upload
                              <input
                                aria-label={`Upload ${label}`}
                                className="sr-only"
                                type="file"
                                accept={
                                  assetKind === "background"
                                    ? "application/pdf,image/png,image/jpeg"
                                    : "image/png,image/jpeg"
                                }
                                disabled={busy}
                                onChange={(event) => {
                                  const file = event.target.files?.[0];
                                  event.target.value = "";
                                  if (file)
                                    void run(async () => {
                                      const form = new FormData();
                                      form.append("file", file);
                                      const result = await api.post(
                                        `${base}/assets?kind=${assetKind}`,
                                        form,
                                      );
                                      setEditHead((current) =>
                                        current
                                          ? {
                                              ...current,
                                              [key]: result.data.id,
                                            }
                                          : current,
                                      );
                                    });
                                }}
                              />
                            </label>
                            {editHead[key] && (
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  setEditHead({ ...editHead, [key]: null })
                                }
                              >
                                Remove
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        PNG or JPEG, up to 2 MB; full-page artwork also accepts
                        a single-page PDF. Use artwork matching the document
                        orientation. Artwork and signatures are stored securely
                        in the database.
                      </p>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={editHead.show_company_header}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              show_company_header: e.target.checked,
                            })
                          }
                        />
                        Show company header (turn off if included in full-page
                        artwork)
                      </label>
                      <Field label="Header text (blank uses company address)">
                        <Textarea
                          maxLength={1000}
                          value={editHead.header_text}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              header_text: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <Field label="Footer text">
                        <Textarea
                          maxLength={1000}
                          value={editHead.footer_text}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              footer_text: e.target.value,
                            })
                          }
                        />
                      </Field>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <Field label="Signatory name">
                          <Input
                            maxLength={150}
                            value={editHead.signatory_name}
                            onChange={(e) =>
                              setEditHead({
                                ...editHead,
                                signatory_name: e.target.value,
                              })
                            }
                          />
                        </Field>
                        <Field label="Signatory title">
                          <Input
                            required
                            maxLength={150}
                            value={editHead.signatory_title}
                            onChange={(e) =>
                              setEditHead({
                                ...editHead,
                                signatory_title: e.target.value,
                              })
                            }
                          />
                        </Field>
                      </div>
                      <div className="grid gap-4 sm:grid-cols-3">
                        <Field label="Accent colour">
                          <Input
                            type="color"
                            value={editHead.accent_color}
                            onChange={(e) =>
                              setEditHead({
                                ...editHead,
                                accent_color: e.target.value,
                              })
                            }
                          />
                        </Field>
                        <Field label="Top margin (mm)">
                          <Input
                            type="number"
                            min={30}
                            max={90}
                            required
                            value={editHead.top_margin_mm}
                            onChange={(e) =>
                              setEditHead({
                                ...editHead,
                                top_margin_mm: Number(e.target.value),
                              })
                            }
                          />
                        </Field>
                        <Field label="Bottom margin (mm)">
                          <Input
                            type="number"
                            min={20}
                            max={60}
                            required
                            value={editHead.bottom_margin_mm}
                            onChange={(e) =>
                              setEditHead({
                                ...editHead,
                                bottom_margin_mm: Number(e.target.value),
                              })
                            }
                          />
                        </Field>
                      </div>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={editHead.is_active}
                          onChange={(e) =>
                            setEditHead({
                              ...editHead,
                              is_active: e.target.checked,
                            })
                          }
                        />
                        Active letterhead
                      </label>
                      <Button disabled={busy}>
                        <Save className="mr-2 h-4 w-4" />
                        Save letterhead
                      </Button>
                    </CompactForm>
                  </SmartCreateSection>
                )}
              </section>
            </div>
          )}
          {tab === "Issued" && (
            <section className={`${panelClass} space-y-4`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="font-semibold">
                  Issued documents ({history.data?.total || 0})
                </h2>
                <Input
                  className="max-w-sm"
                  placeholder="Find recipient or reference…"
                  value={historySearch}
                  onChange={(e) => {
                    setHistorySearch(e.target.value);
                    setHistoryPage(0);
                  }}
                />
              </div>
              <div className="flex flex-wrap items-end gap-3">
                <label className="text-xs">
                  Status
                  <NativeSelect
                    aria-label="Issued status"
                    value={historyFilters.status}
                    onChange={(e) => {
                      setHistoryFilters({
                        ...historyFilters,
                        status: e.target.value,
                      });
                      setHistoryPage(0);
                    }}
                  >
                    <option value="">All statuses</option>
                    <option>Issued</option>
                    <option>Revoked</option>
                  </NativeSelect>
                </label>
                {[
                  ["issue_from", "Issued from"],
                  ["issue_to", "Issued until"],
                ].map(([key, label]) => (
                  <label className="text-xs" key={key}>
                    {label}
                    <Input
                      type="date"
                      aria-label={label}
                      value={historyFilters[key as keyof typeof historyFilters]}
                      onChange={(e) => {
                        setHistoryFilters({
                          ...historyFilters,
                          [key]: e.target.value,
                        });
                        setHistoryPage(0);
                      }}
                    />
                  </label>
                ))}
                <label className="text-xs">
                  Sort
                  <NativeSelect
                    aria-label="Issued sort"
                    value={historyFilters.sort}
                    onChange={(e) =>
                      setHistoryFilters({
                        ...historyFilters,
                        sort: e.target.value,
                      })
                    }
                  >
                    <option value="issued_at">Recently issued</option>
                    <option value="issue_date">Issue date</option>
                    <option value="title">Document name</option>
                  </NativeSelect>
                </label>
              </div>
              <p className="text-sm text-muted-foreground">
                Reprints use the data and letterhead version saved at issuance.
                Revoked copies carry a watermark.
              </p>
              {history.isError && (
                <p role="alert">
                  Unable to load issued documents. Please refresh.
                </p>
              )}
              <div className="space-y-3">
                {history.data?.items.map((item) => (
                  <article
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4"
                  >
                    <div>
                      <h3 className="font-medium">{item.title}</h3>
                      <p className="text-sm">{item.recipient_name}</p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {item.reference} · {item.issue_date} · Template v
                        {item.template_version} · {item.status}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {item.template_name || "Saved template"} · Issued by{" "}
                        {item.issuer_name || "authorized HR"}
                      </p>
                      {item.revoke_reason && (
                        <p className="mt-1 text-sm text-destructive">
                          Revocation: {item.revoke_reason}
                        </p>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => void run(() => viewIssued(item))}
                      >
                        <Eye size={15} />
                        View
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => void run(() => shareIssued(item))}
                      >
                        <Send size={15} />
                        Share
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => void run(() => download(item))}
                      >
                        <Download className="mr-2 h-4 w-4" />
                        Download
                      </Button>
                      {item.status !== "Revoked" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setRevoke(item);
                            setReason("");
                          }}
                        >
                          Revoke
                        </Button>
                      )}
                    </div>
                  </article>
                ))}
                {history.data?.total === 0 && (
                  <p className="py-10 text-center text-muted-foreground">
                    No documents issued yet.
                  </p>
                )}
              </div>
              <div className="flex justify-end gap-2">
                <Button
                  variant="outline"
                  disabled={!historyPage || history.isFetching}
                  onClick={() => setHistoryPage((p) => p - 1)}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  disabled={
                    history.isFetching ||
                    (historyPage + 1) * 30 >= (history.data?.total || 0)
                  }
                  onClick={() => setHistoryPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </section>
          )}
        </>
      )}
      <Dialog
        open={!!issuedPreview}
        onOpenChange={(v) => !v && setIssuedPreview(null)}
      >
        <DialogContent className="dv-review-dialog">
          <DialogTitle>{issuedPreview?.title}</DialogTitle>
          {issuedPreview && (
            <Suspense fallback={<p role="status">Loading issued PDF…</p>}>
              <PdfPreview file={issuedPreview.file} zoomControls />
            </Suspense>
          )}
        </DialogContent>
      </Dialog>
      {revoke && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="revoke-title"
        >
          <CompactForm
            className="w-full max-w-md space-y-4 rounded-xl bg-background p-6"
            onSubmit={(e) => {
              e.preventDefault();
              void run(async () => {
                await api.post(`${base}/issued/${revoke.id}/revoke`, {
                  reason,
                });
                setRevoke(null);
                await refresh();
              });
            }}
          >
            <h2 id="revoke-title" className="font-semibold">
              Revoke {revoke.reference}
            </h2>
            <p className="text-sm">
              The original remains in the register with its reason and a revoked
              watermark.
            </p>
            <Field label="Reason">
              <Textarea
                autoFocus
                required
                minLength={5}
                maxLength={1000}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              />
            </Field>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => setRevoke(null)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={busy || reason.trim().length < 5}
              >
                Revoke document
              </Button>
            </div>
          </CompactForm>
        </div>
      )}
    </div>
  );
}
